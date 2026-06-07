"""test_lottery_exceptions — 异常层次测试
=====================================
高内聚：只测试异常类的构造、继承链、结构化输出。
低耦合：不依赖任何 lottery 模块（仅依赖父项目 exceptions 基类）。
崩溃安全：验证异常链式传递，确保捕获 CapabilityShelfError 能兜底所有子类。
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from ai_capability_shelf.exceptions import CapabilityShelfError
from ai_capability_shelf.lottery.exceptions import (
    CacheNotFoundError,
    ConfigError,
    DataExtractionError,
    DbConnectionError,
    DbQueryError,
    LotteryEngineError,
    LotteryError,
    NoParticipantsError,
    SeedGenerationError,
    WeightComputationError,
)

# ── 层次结构 ──────────────────────────────────────────────


class TestLotteryExceptionHierarchy:
    """验证 LotteryError 继承 CapabilityShelfError，所有子类继承 LotteryError"""

    def test_base_inherits_capability_shelf(self) -> None:
        assert issubclass(LotteryError, CapabilityShelfError)

    def test_config_error_inherits_lottery(self) -> None:
        assert issubclass(ConfigError, LotteryError)

    def test_data_extraction_inherits_lottery(self) -> None:
        assert issubclass(DataExtractionError, LotteryError)

    def test_cache_not_found_inherits_data_extraction(self) -> None:
        assert issubclass(CacheNotFoundError, DataExtractionError)

    def test_db_connection_inherits_data_extraction_and_persistence(self) -> None:
        assert issubclass(DbConnectionError, DataExtractionError)

    def test_db_query_inherits_data_extraction(self) -> None:
        assert issubclass(DbQueryError, DataExtractionError)

    def test_weight_computation_inherits_lottery(self) -> None:
        assert issubclass(WeightComputationError, LotteryError)

    def test_seed_generation_inherits_lottery(self) -> None:
        assert issubclass(SeedGenerationError, LotteryError)

    def test_lottery_engine_inherits_lottery(self) -> None:
        assert issubclass(LotteryEngineError, LotteryError)

    def test_no_participants_inherits_engine(self) -> None:
        assert issubclass(NoParticipantsError, LotteryEngineError)

    def test_all_subclasses_caught_by_capability_shelf(self) -> None:
        """验证捕获 CapabilityShelfError 能兜底所有抽奖异常"""
        all_exceptions = [
            LotteryError,
            ConfigError,
            DataExtractionError,
            CacheNotFoundError,
            DbConnectionError,
            DbQueryError,
            WeightComputationError,
            SeedGenerationError,
            LotteryEngineError,
            NoParticipantsError,
        ]
        for exc in all_exceptions:
            assert issubclass(exc, CapabilityShelfError), f"{exc.__name__} 不在 CapabilityShelfError 层次中"


# ── 构造与消息 ────────────────────────────────────────────


class TestExceptionConstruction:
    """验证异常构造默认值、自定义消息、code、detail、context"""

    def test_lottery_error_default(self) -> None:
        exc = LotteryError()
        assert exc.code == "UNKNOWN"
        assert exc.message == ""
        assert exc.detail == ""
        assert exc.context == {}

    def test_config_error_default_message(self) -> None:
        exc = ConfigError()
        assert exc.code == "LOTTERY_CONFIG"
        assert "配置" in exc.message

    def test_config_error_custom(self) -> None:
        exc = ConfigError(
            "自定义配置错误",
            detail="缺少 NOTE_ID",
            context={"env_var": "NOTE_ID"},
        )
        assert exc.code == "LOTTERY_CONFIG"
        assert exc.message == "自定义配置错误"
        assert "缺少" in exc.detail
        assert exc.context["env_var"] == "NOTE_ID"

    def test_data_extraction_error_default(self) -> None:
        exc = DataExtractionError()
        assert exc.code == "DATA_EXTRACTION"
        assert "提取" in exc.message

    def test_cache_not_found_no_extra_args(self) -> None:
        """CacheNotFoundError 简单继承，无额外构造参数"""
        exc = CacheNotFoundError()
        assert isinstance(exc, DataExtractionError)
        # 无自定义构造，默认使用父类 DataExtractionError 的默认值
        assert exc.code == "DATA_EXTRACTION"

    def test_db_connection_dual_inheritance(self) -> None:
        exc = DbConnectionError("DB 连接超时", detail="timeout=10s")
        assert isinstance(exc, DataExtractionError)
        assert exc.code == "DATA_EXTRACTION"
        assert "超时" in exc.detail

    def test_db_query_error(self) -> None:
        exc = DbQueryError("查询异常", detail="列不存在")
        assert exc.code == "DATA_EXTRACTION"

    def test_weight_computation_default(self) -> None:
        exc = WeightComputationError()
        assert exc.code == "WEIGHT_COMPUTE"
        assert "权重" in exc.message

    def test_weight_computation_custom(self) -> None:
        exc = WeightComputationError("除数异常", detail="weights 总和为 0")
        assert exc.detail == "weights 总和为 0"

    def test_seed_generation_default(self) -> None:
        exc = SeedGenerationError()
        assert exc.code == "SEED_GENERATION"

    def test_seed_generation_custom(self) -> None:
        exc = SeedGenerationError("哈希计算异常", detail="SHA-256 失败")
        assert exc.code == "SEED_GENERATION"

    def test_engine_error_default(self) -> None:
        exc = LotteryEngineError()
        # LotteryEngineError 简单继承，code 用父类默认
        assert isinstance(exc, LotteryError)
        assert exc.code == "UNKNOWN"

    def test_no_participants_default(self) -> None:
        exc = NoParticipantsError()
        assert exc.code == "NO_PARTICIPANTS"
        assert "参与者" in exc.message

    def test_no_participants_custom(self) -> None:
        exc = NoParticipantsError(
            "自定义无参与者",
            detail="所有评论均被短评论过滤",
            context={"excluded": 300},
        )
        assert exc.code == "NO_PARTICIPANTS"
        assert exc.context["excluded"] == 300


# ── 结构化输出 ────────────────────────────────────────────


class TestExceptionStructuredOutput:
    """验证 to_dict() 行为"""

    def test_to_dict_minimal(self) -> None:
        exc = LotteryError()
        d = exc.to_dict()
        assert d["code"] == "UNKNOWN"
        assert "message" in d
        assert "detail" in d
        assert "context" in d

    def test_to_dict_full(self) -> None:
        exc = ConfigError(
            "缺少配置",
            detail="NOTE_ID 缺失",
            context={"env": ".env"},
        )
        d = exc.to_dict()
        assert d["code"] == "LOTTERY_CONFIG"
        assert d["message"] == "缺少配置"
        assert d["detail"] == "NOTE_ID 缺失"
        assert d["context"]["env"] == ".env"

    def test_to_dict_preserves_subclass_fields(self) -> None:
        """子类构造参数正确传递到 to_dict"""
        exc = NoParticipantsError(
            detail="全部过滤",
            context={"total": 0},
        )
        d = exc.to_dict()
        assert d["code"] == "NO_PARTICIPANTS"
        assert d["detail"] == "全部过滤"
        assert d["context"]["total"] == 0


# ── 链式异常（崩溃恢复场景模拟） ────────────────────────────


class TestExceptionChaining:
    """验证异常链式传递（断电/崩溃场景下异常来源追溯）"""

    def test_chain_via_raise_from(self) -> None:
        """模拟管线执行中 DB 连接失败 → DataExtractionError 链式传递"""
        try:
            try:
                raise ConnectionError("database is down")
            except ConnectionError as e:
                raise DbConnectionError("DB 连接失败", context={"cause": str(e)}) from e
        except CapabilityShelfError as e:
            assert isinstance(e, DbConnectionError)
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ConnectionError)

    def test_catch_base_catches_all(self) -> None:
        """捕获 CapabilityShelfError 可捕获任何抽奖异常子类"""
        for exc_class in [ConfigError, DataExtractionError, NoParticipantsError]:
            try:
                raise exc_class("test")
            except CapabilityShelfError:
                pass  # OK
            except Exception:
                pytest.fail(f"{exc_class.__name__} 未被 CapabilityShelfError 捕获")
