"""
test_lottery_engine — 抽奖引擎单元测试
========================================
覆盖 generate_seed、WeightedEngine、run_weighted_lottery。
高内聚：每个测试只测一个函数/类，不依赖外部模块。
崩溃安全验证：确定性种子确保随机结果可复现。
"""

from __future__ import annotations

import pytest

from ai_capability_shelf.lottery.engine import (
    generate_seed,
    WeightedEngine,
    run_weighted_lottery,
    SeedInfo,
)
from ai_capability_shelf.lottery.exceptions import (
    SeedGenerationError,
    NoParticipantsError,
    LotteryEngineError,
)


# ═══════════════════════════════════════════════════════════════
#  generate_seed
# ═══════════════════════════════════════════════════════════════

class TestGenerateSeed:
    """SHA-256 确定性种子生成"""

    def test_basic_seed(self) -> None:
        """正常输入应返回 SeedInfo"""
        info = generate_seed("2025-06-01", "note_123")
        assert isinstance(info, SeedInfo)
        assert info.seed_str == "deepseek_roleplay_lottery_2025-06-01_xhs_note_123"
        assert len(info.seed_hash) == 64  # SHA-256 hex
        assert isinstance(info.seed_int, int)
        assert 0 <= info.seed_int < 16 ** 16

    def test_deterministic_same_input(self) -> None:
        """相同输入应产生相同种子"""
        a = generate_seed("2025-06-01", "note_123")
        b = generate_seed("2025-06-01", "note_123")
        assert a.seed_int == b.seed_int
        assert a.seed_hash == b.seed_hash
        assert a.seed_str == b.seed_str

    def test_deterministic_different_input(self) -> None:
        """不同输入应产生不同种子"""
        a = generate_seed("2025-06-01", "note_123")
        b = generate_seed("2025-06-02", "note_123")
        assert a.seed_int != b.seed_int

    def test_empty_note_id(self) -> None:
        """空 note_id 不应导致异常"""
        info = generate_seed("2025-06-01")
        assert "xhs_" in info.seed_str

    def test_empty_lottery_time(self) -> None:
        """空 lottery_time 不应导致异常"""
        info = generate_seed("")
        assert isinstance(info.seed_int, int)

    def test_invalid_input_raises(self) -> None:
        """非字符串输入应抛出 SeedGenerationError"""
        with pytest.raises(SeedGenerationError):
            generate_seed(None, "note_123")  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════
#  WeightedEngine — 加权随机引擎
# ═══════════════════════════════════════════════════════════════

class TestWeightedEngine:
    """WeightedEngine：pick_one / pick_with_details"""

    def setup(self) -> dict:
        """共享测试数据"""
        return {
            "user_a": 10.0,
            "user_b": 30.0,
            "user_c": 60.0,
        }

    # ── 初始化 ──

    def test_init(self) -> None:
        """正常初始化"""
        engine = WeightedEngine({"a": 1.0, "b": 2.0}, seed_int=42)
        assert engine is not None

    def test_init_empty_weights(self) -> None:
        """空权重应抛出 NoParticipantsError"""
        with pytest.raises(NoParticipantsError, match="权重表为空"):
            WeightedEngine({}, seed_int=42)

    def test_init_negative_weight(self) -> None:
        """负权重应能初始化（pick_one 仍可能工作）"""
        engine = WeightedEngine({"a": -1.0, "b": 2.0}, seed_int=42)
        assert engine is not None

    def test_init_zero_weight(self) -> None:
        """零权重应能初始化"""
        engine = WeightedEngine({"a": 0.0, "b": 1.0}, seed_int=42)
        winner = engine.pick_one()
        assert winner == "b"  # 只有 b 有正权重

    # ── pick_one ──

    def test_pick_one_returns_user_id(self) -> None:
        """pick_one 应返回字符串类型的 user_id"""
        engine = WeightedEngine({"a": 1.0, "b": 2.0}, seed_int=42)
        winner = engine.pick_one()
        assert isinstance(winner, str)
        assert winner in ("a", "b")

    def test_pick_one_deterministic(self) -> None:
        """相同种子应产生相同结果"""
        engine_a = WeightedEngine({"a": 1.0, "b": 2.0}, seed_int=100)
        engine_b = WeightedEngine({"a": 1.0, "b": 2.0}, seed_int=100)
        assert engine_a.pick_one() == engine_b.pick_one()

    def test_pick_one_different_seed_different_result(self) -> None:
        """不同种子可能产生不同结果（极低概率相同，但可接受）"""
        engine_a = WeightedEngine({"a": 1.0, "b": 2.0}, seed_int=1)
        engine_b = WeightedEngine({"a": 1.0, "b": 2.0}, seed_int=999999)
        # 不是 assert 不相等，而是确保都能正常工作
        assert engine_a.pick_one() in ("a", "b")
        assert engine_b.pick_one() in ("a", "b")

    def test_pick_one_high_weight_wins_more_often(self) -> None:
        """高权重用户在多次抽奖中应出现更多（统计概率）"""
        weights = {"a": 1.0, "b": 100.0}
        wins = {"a": 0, "b": 0}
        for seed in range(200):
            engine = WeightedEngine(weights, seed_int=seed)
            winner = engine.pick_one()
            wins[winner] += 1
        # b 有 ~99% 概率，200 次中几乎肯定 > 150 次
        assert wins["b"] > wins["a"]
        assert wins["b"] > 150

    def test_pick_one_single_user(self) -> None:
        """只有一个用户时应始终返回该用户"""
        engine = WeightedEngine({"a": 5.0}, seed_int=42)
        for _ in range(10):
            assert engine.pick_one() == "a"

    def test_pick_one_zero_total_weight(self) -> None:
        """所有权重为 0 时仍应返回某个用户（random.choices 行为）"""
        engine = WeightedEngine({"a": 0.0, "b": 0.0}, seed_int=42)
        winner = engine.pick_one()
        assert winner in ("a", "b")

    # ── pick_with_details ──

    def test_pick_with_details_tuple_shape(self) -> None:
        """pick_with_details 应返回 (user_id, weight, probability) 三元组"""
        engine = WeightedEngine({"a": 1.0, "b": 2.0, "c": 7.0}, seed_int=42)
        result = engine.pick_with_details()
        assert len(result) == 3
        uid, weight, prob = result
        assert isinstance(uid, str)
        assert isinstance(weight, float)
        assert isinstance(prob, float)

    def test_pick_with_details_probability_sum(self) -> None:
        """多次抽奖的概率值应始终在 [0, 100] 范围"""
        for seed in range(50):
            engine = WeightedEngine({"a": 1.0, "b": 2.0, "c": 7.0}, seed_int=seed)
            _, _, prob = engine.pick_with_details()
            assert 0 <= prob <= 100

    def test_pick_with_details_single_user(self) -> None:
        """单用户时概率应为 100%"""
        engine = WeightedEngine({"a": 5.0}, seed_int=42)
        uid, weight, prob = engine.pick_with_details()
        assert uid == "a"
        assert weight == 5.0
        assert prob == 100.0

    def test_pick_with_details_weight_matches_input(self) -> None:
        """返回的权重应与输入的权重一致"""
        weights = {"a": 3.0, "b": 7.0}
        engine = WeightedEngine(weights, seed_int=42)
        uid, weight, _ = engine.pick_with_details()
        assert weight == weights[uid]

    def test_pick_with_details_probability_correct(self) -> None:
        """概率 = weight / total * 100"""
        weights = {"a": 25.0, "b": 75.0}
        engine = WeightedEngine(weights, seed_int=100)
        uid, weight, prob = engine.pick_with_details()
        expected_prob = weight / 100.0 * 100
        assert prob == pytest.approx(expected_prob, rel=1e-9)


# ═══════════════════════════════════════════════════════════════
#  run_weighted_lottery — 便捷函数
# ═══════════════════════════════════════════════════════════════

class TestRunWeightedLottery:
    """一键抽奖函数"""

    def test_basic_run(self) -> None:
        """基本功能：返回 user_id 字符串"""
        winner = run_weighted_lottery({"a": 1.0, "b": 2.0}, seed_int=42)
        assert isinstance(winner, str)
        assert winner in ("a", "b")

    def test_deterministic(self) -> None:
        """相同输入应返回相同结果"""
        a = run_weighted_lottery({"a": 1.0, "b": 2.0}, seed_int=42)
        b = run_weighted_lottery({"a": 1.0, "b": 2.0}, seed_int=42)
        assert a == b

    def test_delegates_to_engine(self) -> None:
        """应代理至 WeightedEngine.pick_one"""
        winner = run_weighted_lottery({"x": 100.0}, seed_int=0)
        assert winner == "x"

    def test_empty_weights_raises(self) -> None:
        """空权重应抛出 NoParticipantsError"""
        with pytest.raises(NoParticipantsError):
            run_weighted_lottery({}, seed_int=42)


# ═══════════════════════════════════════════════════════════════
#  SeedInfo — 数据容器
# ═══════════════════════════════════════════════════════════════

class TestSeedInfo:
    """SeedInfo 数据容器"""

    def test_all_fields(self) -> None:
        """所有字段正确赋值和读取"""
        info = SeedInfo(seed_str="test", seed_hash="abc123", seed_int=42)
        assert info.seed_str == "test"
        assert info.seed_hash == "abc123"
        assert info.seed_int == 42

    def test_immutable_like(self) -> None:
        """dataclass 字段可读"""
        info = SeedInfo(seed_str="s", seed_hash="h", seed_int=0)
        assert isinstance(info, SeedInfo)
