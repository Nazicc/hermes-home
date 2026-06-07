"""
lottery.engine — 抽奖引擎
=========================
种子生成 + 加权随机执行。
高内聚：只做"种子+随机选择"。
低耦合：仅依赖 models + exceptions。
"""

from __future__ import annotations

import hashlib
import random
from typing import Dict, List, Tuple
from dataclasses import dataclass

from ai_capability_shelf.lottery.models import WeightTable, WeightEntry, UserData
from ai_capability_shelf.lottery.exceptions import (
    LotteryEngineError,
    NoParticipantsError,
    SeedGenerationError,
)


# ── 种子生成 ────────────────────────────────────────────────


@dataclass
class SeedInfo:
    """种子信息"""
    seed_str: str
    seed_hash: str
    seed_int: int


def generate_seed(lottery_time: str, note_id: str = "") -> SeedInfo:
    """
    生成确定性随机种子。

    种子 = SHA-256(f"deepseek_roleplay_lottery_{time}_{note_id}")
    前 16 位 hex → int。
    """
    try:
        seed_str = f"deepseek_roleplay_lottery_{lottery_time}_xhs_{note_id}"
        seed_hash = hashlib.sha256(seed_str.encode()).hexdigest()
        seed_int = int(seed_hash[:16], 16)
        return SeedInfo(seed_str=seed_str, seed_hash=seed_hash, seed_int=seed_int)
    except (ValueError, AttributeError) as e:
        raise SeedGenerationError(detail=f"种子生成失败: {e}")


# ── 加权随机执行 ────────────────────────────────────────────


class WeightedEngine:
    """
    加权随机抽奖引擎。

    用法：
        engine = WeightedEngine(weights, seed_int)
        winner = engine.pick_one()
        winner_uid, winner_weight, winner_prob = engine.pick_with_details()
    """

    def __init__(
        self,
        weights: Dict[str, float],
        seed_int: int,
    ) -> None:
        if not weights:
            raise NoParticipantsError("权重表为空，无法执行抽奖")

        self._weights = dict(weights)
        self._seed_int = seed_int
        self._total_weight = sum(weights.values())

        # 预排序用户列表保证确定性
        self._users_list: List[str] = sorted(weights.keys())
        self._weights_list: List[float] = [weights[u] for u in self._users_list]

        self._set_rng()

    def _set_rng(self) -> None:
        """设置确定性随机生成器"""
        random.seed(self._seed_int)

    def pick_one(self) -> str:
        """返回中奖 user_id"""
        if not self._users_list:
            raise NoParticipantsError("参与者列表为空")
        try:
            return random.choices(
                self._users_list, weights=self._weights_list, k=1
            )[0]
        except (ValueError, IndexError) as e:
            raise LotteryEngineError(detail=f"随机选择失败: {e}")

    def pick_with_details(self) -> Tuple[str, float, float]:
        """
        返回 (中奖 user_id, 权重, 概率百分比)
        """
        winner = self.pick_one()
        w = self._weights[winner]
        pct = (w / self._total_weight * 100) if self._total_weight > 0 else 0.0
        return winner, w, pct


# ── 便捷函数 ────────────────────────────────────────────────


def calculate_weights(user_data: Dict[str, UserData]) -> Dict[str, float]:
    """
    便捷函数：计算权重（直接传入 UserData dict）。
    导出至 __init__ 供外部调用。
    """
    # 延迟导入避免循环引用
    from ai_capability_shelf.lottery.aggregator import calculate_weights as _calc
    return _calc(user_data)


def run_weighted_lottery(
    weights: Dict[str, float],
    seed_int: int,
) -> str:
    """
    一键执行加权抽奖。
    返回中奖 user_id。
    """
    engine = WeightedEngine(weights, seed_int)
    return engine.pick_one()
