"""
lottery.models — 纯数据模型
===========================
Pydantic v2 模型，零外部依赖（仅 pydantic + datetime）。
高内聚：只定义数据结构，不含业务逻辑。
低耦合：不引用任何其他 lottery 模块。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Comment(BaseModel):
    """单条评论数据"""
    id: str = ""
    user_id: str = ""
    nickname: str = "unknown"
    content: str = ""


class UserData(BaseModel):
    """按 user_id 聚合后的用户数据"""
    user_id: str = ""
    nickname: str = ""
    count: int = 0
    total_length: int = 0
    comments: List[str] = Field(default_factory=list)


class WeightEntry(BaseModel):
    """权重表的一条记录"""
    user_id: str
    display_name: str
    nickname: str
    comment_count: int
    total_length: int
    weight: float
    probability_percent: float = 0.0


class WeightTable(BaseModel):
    """完整权重表"""
    entries: List[WeightEntry] = Field(default_factory=list)
    total_weight: float = 0.0
    participant_count: int = 0

    def sorted_by_weight_desc(self) -> List[WeightEntry]:
        """按权重降序排列（带缓存）"""
        return sorted(self.entries, key=lambda e: -e.weight)


class LotteryConfig(BaseModel):
    """抽奖运行配置"""
    note_id: str = ""
    lottery_time_str: str = ""
    exclude_user_id: Optional[str] = None
    min_comment_length: int = 5
    cache_path: str = ""
    db_host: str = ""
    db_port: int = 5432
    db_name: str = "xhs"
    db_user: str = ""
    db_password: str = ""
    db_connect_timeout: int = 10

    # 崩溃安全配置
    data_dir: str = ""
    enable_sentinel: bool = True
    enable_checkpoint: bool = True

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        # 默认排除敏感字段
        exclude = {"db_password", "__pwd__"}
        return super().model_dump(exclude=exclude, **kwargs)


class LotteryResult(BaseModel):
    """抽奖最终结果（含所有中间数据）"""
    # 基础信息
    lottery_time: str = ""
    note_id: str = ""
    seed_str: str = ""
    seed_hash: str = ""
    seed_int: int = 0

    # 数据统计
    total_comments: int = 0
    total_participants: int = 0

    # 权重表
    weight_table: WeightTable = Field(default_factory=WeightTable)

    # 中奖者
    winner_user_id: str = ""
    winner_display_name: str = ""
    winner_weight: float = 0.0
    winner_probability: float = 0.0
    winner_comments: List[str] = Field(default_factory=list)

    # 元数据
    data_source: str = ""  # "db" | "cache" | "unknown"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    recovered_from_crash: bool = False

    @property
    def winner_summary(self) -> str:
        """简洁的中奖摘要"""
        return (
            f"🎉 中奖用户: 【{self.winner_display_name}】\n"
            f"  权重: {self.winner_weight:.2f} | 概率: {self.winner_probability:.3f}%\n"
            f"  评论: {len(self.winner_comments)} 条, "
            f"共 {sum(len(c) for c in self.winner_comments)} 字"
        )
