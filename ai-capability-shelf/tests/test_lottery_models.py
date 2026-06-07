"""
test_lottery_models.py — 纯数据模型单元测试
===========================================
测试 Comment, UserData, WeightEntry, WeightTable, LotteryConfig, LotteryResult。
高内聚：仅依赖 models.py，零外部 I/O。
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_capability_shelf.lottery.models import (
    Comment,
    LotteryConfig,
    LotteryResult,
    UserData,
    WeightEntry,
    WeightTable,
)


class TestComment:
    """Comment — 单条评论"""

    def test_minimal_creation(self) -> None:
        c = Comment()
        assert c.id == ""
        assert c.user_id == ""
        assert c.nickname == "unknown"
        assert c.content == ""

    def test_full_creation(self) -> None:
        c = Comment(id="c1", user_id="u1", nickname="测试", content="Hello")
        assert c.id == "c1"
        assert c.user_id == "u1"
        assert c.nickname == "测试"
        assert c.content == "Hello"

    def test_frozen(self) -> None:
        c = Comment(id="c1", user_id="u1", nickname="N", content="C")
        with pytest.raises(ValidationError):
            c.user_id = "changed"

    def test_equality(self) -> None:
        c1 = Comment(id="c1", user_id="u1", nickname="N", content="C")
        c2 = Comment(id="c1", user_id="u1", nickname="N", content="C")
        assert c1 == c2


class TestUserData:
    """UserData — 聚合后的用户数据"""

    def test_minimal_creation(self) -> None:
        u = UserData()
        assert u.user_id == ""
        assert u.nickname == ""
        assert u.count == 0
        assert u.total_length == 0
        assert u.comments == []

    def test_full_creation(self) -> None:
        u = UserData(user_id="u1", nickname="用户1", count=5, total_length=100, comments=["c1", "c2"])
        assert u.user_id == "u1"
        assert u.nickname == "用户1"
        assert u.count == 5
        assert u.total_length == 100
        assert u.comments == ["c1", "c2"]

    def test_frozen(self) -> None:
        u = UserData(user_id="u1", nickname="N", count=1, total_length=1)
        with pytest.raises(ValidationError):
            u.nickname = "changed"

    def test_equality(self) -> None:
        u1 = UserData(user_id="u1", nickname="N", count=1, total_length=1)
        u2 = UserData(user_id="u1", nickname="N", count=1, total_length=1)
        assert u1 == u2

    def test_default_comments_list(self) -> None:
        u = UserData(user_id="u1", nickname="N", count=0, total_length=0)
        assert u.comments == []


class TestWeightEntry:
    """WeightEntry — 权重条目"""

    def test_full_creation(self) -> None:
        w = WeightEntry(
            user_id="u1",
            display_name="用户1",
            nickname="用户1",
            comment_count=5,
            total_length=100,
            weight=15.5,
            probability_percent=25.0,
        )
        assert w.user_id == "u1"
        assert w.display_name == "用户1"
        assert w.nickname == "用户1"
        assert w.comment_count == 5
        assert w.total_length == 100
        assert w.weight == 15.5
        assert w.probability_percent == 25.0

    def test_default_probability(self) -> None:
        w = WeightEntry(
            user_id="u1", display_name="N", nickname="N",
            comment_count=1, total_length=10, weight=1.0,
        )
        assert w.probability_percent == 0.0

    def test_int_weight(self) -> None:
        w = WeightEntry(
            user_id="u1", display_name="N", nickname="N",
            comment_count=1, total_length=10, weight=10,
        )
        assert w.weight == 10.0
        assert isinstance(w.weight, float)

    def test_frozen(self) -> None:
        w = WeightEntry(
            user_id="u1", display_name="N", nickname="N",
            comment_count=1, total_length=10, weight=1.0,
        )
        with pytest.raises(ValidationError):
            w.weight = 2.0

    def test_zero_weight(self) -> None:
        w = WeightEntry(
            user_id="u0", display_name="Z", nickname="Z",
            comment_count=0, total_length=0, weight=0.0,
        )
        assert w.weight == 0.0


class TestWeightTable:
    """WeightTable — 权重表容器"""

    @pytest.fixture
    def sample_entries(self) -> list[WeightEntry]:
        return [
            WeightEntry(user_id="u1", display_name="A", nickname="A", comment_count=2, total_length=20, weight=10.0),
            WeightEntry(user_id="u2", display_name="B", nickname="B", comment_count=4, total_length=40, weight=20.0),
            WeightEntry(user_id="u3", display_name="C", nickname="C", comment_count=6, total_length=60, weight=30.0),
        ]

    def test_empty_table(self) -> None:
        wt = WeightTable()
        assert wt.entries == []
        assert wt.total_weight == 0.0
        assert wt.participant_count == 0

    def test_with_entries(self, sample_entries) -> None:
        wt = WeightTable(entries=sample_entries)
        assert len(wt.entries) == 3
        assert wt.total_weight == 60.0
        assert wt.participant_count == 3

    def test_frozen(self) -> None:
        wt = WeightTable()
        with pytest.raises(ValidationError):
            wt.total_weight = 999.0

    def test_sorted_by_weight_desc(self, sample_entries) -> None:
        wt = WeightTable(entries=sample_entries)
        sorted_ = wt.sorted_by_weight_desc()
        assert [e.weight for e in sorted_] == [30.0, 20.0, 10.0]
        # 原列表不变
        assert [e.weight for e in wt.entries] == [10.0, 20.0, 30.0]


class TestLotteryConfig:
    """LotteryConfig — 抽奖配置"""

    def test_minimal_config(self) -> None:
        cfg = LotteryConfig()
        assert cfg.note_id == ""
        assert cfg.lottery_time_str == ""
        assert cfg.exclude_user_id is None
        assert cfg.min_comment_length == 5
        assert cfg.cache_path == ""
        assert cfg.db_port == 5432
        assert cfg.db_name == "xhs"
        assert cfg.enable_sentinel is True
        assert cfg.enable_checkpoint is True

    def test_full_config(self) -> None:
        cfg = LotteryConfig(
            note_id="note123",
            lottery_time_str="2025-06-01T12:00:00",
            exclude_user_id="u_exclude",
            min_comment_length=10,
            cache_path="/tmp/cache.json",
            data_dir="/tmp/lottery-data",
            db_host="localhost",
            db_port=3306,
            db_name="test_db",
            db_user="admin",
            db_password="secret",
            db_connect_timeout=5,
            enable_sentinel=False,
            enable_checkpoint=False,
        )
        assert cfg.note_id == "note123"
        assert cfg.lottery_time_str == "2025-06-01T12:00:00"
        assert cfg.exclude_user_id == "u_exclude"
        assert cfg.cache_path == "/tmp/cache.json"
        assert cfg.data_dir == "/tmp/lottery-data"
        assert cfg.db_host == "localhost"
        assert cfg.db_port == 3306

    def test_model_dump_excludes_password(self) -> None:
        cfg = LotteryConfig(note_id="n1", lottery_time_str="t1", db_password="supersecret")
        dumped = cfg.model_dump()
        assert "db_password" not in dumped
        assert dumped["note_id"] == "n1"

    def test_frozen(self) -> None:
        cfg = LotteryConfig(note_id="n1", lottery_time_str="t1")
        with pytest.raises(ValidationError):
            cfg.note_id = "n2"


class TestLotteryResult:
    """LotteryResult — 抽奖结果"""

    def test_minimal_result(self) -> None:
        result = LotteryResult()
        assert result.lottery_time == ""
        assert result.note_id == ""
        assert result.seed_str == ""
        assert result.seed_hash == ""
        assert result.seed_int == 0
        assert result.total_comments == 0
        assert result.total_participants == 0
        assert result.winner_user_id == ""
        assert result.winner_display_name == ""
        assert result.winner_weight == 0.0
        assert result.winner_probability == 0.0
        assert result.winner_comments == []
        assert result.data_source == ""
        assert result.recovered_from_crash is False
        # weight_table 应自动创建
        assert isinstance(result.weight_table, WeightTable)

    def test_full_result(self) -> None:
        wt = WeightTable(
            entries=[WeightEntry(user_id="u1", display_name="胜者", nickname="胜者",
                                 comment_count=3, total_length=50, weight=42.0)],
        )
        result = LotteryResult(
            lottery_time="2025-06-01T12:00:00",
            note_id="note123",
            seed_str="2025-06-01",
            seed_hash="abc123def456",
            seed_int=123456,
            total_comments=10,
            total_participants=5,
            weight_table=wt,
            winner_user_id="u1",
            winner_display_name="胜者",
            winner_weight=42.0,
            winner_probability=15.5,
            winner_comments=["好文!", "支持!"],
            data_source="db",
            recovered_from_crash=True,
        )
        assert result.lottery_time == "2025-06-01T12:00:00"
        assert result.seed_hash == "abc123def456"
        assert result.seed_int == 123456
        assert result.winner_user_id == "u1"
        assert result.winner_weight == 42.0
        assert result.winner_probability == 15.5
        assert len(result.winner_comments) == 2
        assert result.data_source == "db"
        assert result.recovered_from_crash is True
        assert result.weight_table.participant_count == 1

    def test_winner_summary_property(self) -> None:
        result = LotteryResult(
            winner_display_name="胜者",
            winner_weight=42.0,
            winner_probability=15.5,
            winner_comments=["好文!", "支持!", "加油!"],
        )
        summary = result.winner_summary
        assert "🎉" in summary
        assert "胜者" in summary
        assert "42.00" in summary
        assert "15.500" in summary
        assert "3 条" in summary

    def test_created_at_auto_generated(self) -> None:
        result = LotteryResult()
        assert result.created_at != ""
        assert "T" in result.created_at  # ISO 格式含 T

    def test_frozen(self) -> None:
        result = LotteryResult()
        with pytest.raises(ValidationError):
            result.winner_user_id = "changed"

    def test_equality(self) -> None:
        r1 = LotteryResult(lottery_time="t1")
        r2 = LotteryResult(lottery_time="t1")
        # created_at 是动态生成的，所以不相等
        assert r1 != r2
