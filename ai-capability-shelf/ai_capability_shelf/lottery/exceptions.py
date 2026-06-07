"""
lottery.exceptions — 抽奖专属异常层次
======================================
继承 CapabilityShelfError 基类，保持与父项目的异常体系一致。
高内聚：只定义异常类。
低耦合：仅依赖父项目 exceptions，不引用其他 lottery 模块。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ai_capability_shelf.exceptions import (
    CapabilityShelfError,
    PersistenceError,
)


class LotteryError(CapabilityShelfError):
    """抽奖模块基类异常"""


class ConfigError(LotteryError):
    """配置错误 — 缺少必需的环境变量或参数"""

    def __init__(
        self, message: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message or "抽奖配置错误",
            code="LOTTERY_CONFIG",
            detail=detail,
            context=context,
        )


class DataExtractionError(LotteryError):
    """数据提取失败 — DB 连接失败 / 缓存文件不存在 / 格式错误"""

    def __init__(
        self, message: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message or "评论数据提取失败",
            code="DATA_EXTRACTION",
            detail=detail,
            context=context,
        )


class CacheNotFoundError(DataExtractionError):
    """缓存文件不存在"""


class DbConnectionError(DataExtractionError, PersistenceError):
    """数据库连接失败（双重继承：lottery + 持久化语义）"""


class DbQueryError(DataExtractionError):
    """数据库查询失败"""


class WeightComputationError(LotteryError):
    """权重计算失败 — 异常数据导致公式崩溃"""

    def __init__(
        self, message: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message or "权重计算失败",
            code="WEIGHT_COMPUTE",
            detail=detail,
            context=context,
        )


class SeedGenerationError(LotteryError):
    """种子生成失败 — 哈希/种子计算异常"""

    def __init__(
        self, message: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message or "随机种子生成失败",
            code="SEED_GENERATION",
            detail=detail,
            context=context,
        )


class LotteryEngineError(LotteryError):
    """抽奖引擎执行失败 — 加权随机选择异常"""


class NoParticipantsError(LotteryEngineError):
    """无合格参与者 — 所有评论均被过滤"""

    def __init__(
        self, message: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message or "无合格抽奖参与者",
            code="NO_PARTICIPANTS",
            detail=detail,
            context=context,
        )
