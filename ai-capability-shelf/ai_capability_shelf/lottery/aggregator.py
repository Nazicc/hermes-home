"""
lottery.aggregator — 用户聚合 + 权重公式
=========================================
纯函数模块：输入 Comment[] → 输出 WeightTable。
高内聚：只做聚合和权重计算。
低耦合：仅依赖 models 模块。
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Dict, List

from ai_capability_shelf.lottery.models import (
    Comment,
    UserData,
    WeightEntry,
    WeightTable,
)
from ai_capability_shelf.lottery.exceptions import (
    NoParticipantsError,
    WeightComputationError,
)


# ── 核心公开 API ────────────────────────────────────────────


def aggregate_users(
    comments: List[Comment],
    *,
    exclude_user_id: str = "",
    min_comment_length: int = 5,
) -> Dict[str, UserData]:
    """
    按 user_id 聚合评论数据。

    过滤规则：
    - 排除帖主（exclude_user_id）
    - 过滤短评论（< min_comment_length 字符）
    """
    user_map: Dict[str, UserData] = {}

    for c in comments:
        uid = c.user_id
        content = c.content.strip()

        if len(content) < min_comment_length:
            continue
        if exclude_user_id and uid == exclude_user_id:
            continue

        if uid not in user_map:
            user_map[uid] = UserData(user_id=uid, nickname=c.nickname)

        user_map[uid].count += 1
        user_map[uid].total_length += len(content)
        user_map[uid].comments.append(content)
        # 保留最新的昵称
        if c.nickname and c.nickname != "unknown":
            user_map[uid].nickname = c.nickname

    if not user_map:
        raise NoParticipantsError(
            detail="所有评论均被过滤（无合格参与者）",
            context={
                "total_comments": len(comments),
                "exclude_user_id": exclude_user_id,
                "min_comment_length": min_comment_length,
            },
        )

    return user_map


def get_display_names(user_data: Dict[str, UserData]) -> Dict[str, str]:
    """
    生成展示名：同昵称用户用 '#user_id后4位' 区分。
    纯函数 —— 输入用户数据，输出 display_name 映射。
    """
    nick_count: Dict[str, int] = Counter(
        d.nickname for d in user_data.values()
    )
    display_names: Dict[str, str] = {}
    for uid, d in user_data.items():
        if nick_count[d.nickname] > 1:
            display_names[uid] = f"{d.nickname}#{uid[-4:]}"
        else:
            display_names[uid] = d.nickname
    return display_names


def calculate_weights(user_data: Dict[str, UserData]) -> Dict[str, float]:
    """
    计算抽奖权重。

    公式: sqrt(总评论字数) × log₂(评论条数 + 1)

    设计理由:
    - sqrt(字数)：鼓励详细反馈，但避免超长评论获得过大优势
    - log₂(条数+1)：鼓励多次参与，但避免刷量碾压
    - 两者相乘：同时考虑反馈质量（长度）和参与度（次数）
    """
    try:
        weights: Dict[str, float] = {}
        for uid, data in user_data.items():
            length_score = math.sqrt(data.total_length)
            count_score = math.log2(data.count + 1)
            weights[uid] = length_score * count_score
        return weights
    except (ValueError, ArithmeticError) as e:
        raise WeightComputationError(
            detail=f"权重计算异常: {e}",
        )


def build_weight_table(
    weights: Dict[str, float],
    user_data: Dict[str, UserData],
    display_names: Dict[str, str],
) -> WeightTable:
    """构建完整的 WeightTable（含概率百分比）"""
    total_weight = sum(weights.values())
    entries: List[WeightEntry] = []
    for uid, w in sorted(weights.items(), key=lambda x: -x[1]):
        ud = user_data[uid]
        entries.append(
            WeightEntry(
                user_id=uid,
                display_name=display_names.get(uid, ud.nickname) or ud.nickname,
                nickname=ud.nickname,
                comment_count=ud.count,
                total_length=ud.total_length,
                weight=w,
                probability_percent=(w / total_weight * 100) if total_weight > 0 else 0.0,
            )
        )
    return WeightTable(
        entries=entries,
        total_weight=total_weight,
        participant_count=len(entries),
    )


def get_duplicate_nicknames(
    user_data: Dict[str, UserData],
) -> Dict[str, int]:
    """统计同昵称用户分布"""
    counter: Dict[str, int] = Counter(
        d.nickname for d in user_data.values()
    )
    return {k: v for k, v in counter.items() if v > 1}
