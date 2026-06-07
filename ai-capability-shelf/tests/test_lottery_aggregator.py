"""test_lottery_aggregator — 聚合层测试
=====================================
高内聚：只测试数据聚合/权重计算逻辑，不依赖 providers/engine。
低耦合：接收 List[Comment] 输入，返回纯数据结构。
崩溃安全：验证空输入/空评论/零权重等边缘不崩溃。
"""

from __future__ import annotations

import math
from typing import Dict, List

import pytest

from ai_capability_shelf.lottery.models import Comment, UserData, WeightEntry, WeightTable
from ai_capability_shelf.lottery.aggregator import (
    aggregate_users,
    get_display_names,
    calculate_weights,
    build_weight_table,
    get_duplicate_nicknames,
)


# ── 样本数据 ──────────────────────────────────────────────


@pytest.fixture
def simple_comments() -> List[Comment]:
    """3位用户，共6条评论"""
    return [
        Comment(id="c01", user_id="u1", nickname="Alice", content="这是一个很好的评论内容"),
        Comment(id="c02", user_id="u1", nickname="Alice", content="Alice 的第二条评论"),
        Comment(id="c03", user_id="u2", nickname="Bob", content="Bob 的评论"),
        Comment(id="c04", user_id="u2", nickname="Bob", content="Bob 的另一条评论"),
        Comment(id="c05", user_id="u2", nickname="Bob", content="Bob 的第三条评论"),
        Comment(id="c06", user_id="u3", nickname="Charlie", content="Charlie 的长评论来了来了来了来了"),
    ]


@pytest.fixture
def short_comments() -> List[Comment]:
    """含短评论（需要过滤）"""
    return [
        Comment(id="c01", user_id="u1", nickname="Alice", content="正常评论内容"),
        Comment(id="c02", user_id="u1", nickname="Alice", content="短"),  # <5
        Comment(id="c03", user_id="u1", nickname="Alice", content="hi"),  # <5
        Comment(id="c04", user_id="u2", nickname="Bob", content="OK"),     # <5
        Comment(id="c05", user_id="u2", nickname="Bob", content="另一条有效评论内容"),
    ]


# ── 用户聚合 ──────────────────────────────────────────────


class TestAggregateUsers:
    """验证 aggregate_users 逻辑"""

    def test_basic_aggregation(self, simple_comments: List[Comment]) -> None:
        """基本聚合：评论按 user_id 分组"""
        result = aggregate_users(simple_comments)
        assert len(result) == 3
        assert "u1" in result and "u2" in result and "u3" in result

    def test_user_data_counts(self, simple_comments: List[Comment]) -> None:
        """聚合后评论数和总字数正确"""
        result = aggregate_users(simple_comments)
        assert result["u1"].count == 2
        assert result["u1"].total_length == len("这是一个很好的评论内容") + len("Alice 的第二条评论")
        assert result["u2"].count == 3
        assert result["u3"].count == 1

    def test_user_comments_list(self, simple_comments: List[Comment]) -> None:
        """聚合后保留评论文本列表"""
        result = aggregate_users(simple_comments)
        assert len(result["u1"].comments) == 2
        assert result["u1"].comments[0] == "这是一个很好的评论内容"
        assert result["u2"].comments[2] == "Bob 的第三条评论"

    def test_nickname_preserved(self, simple_comments: List[Comment]) -> None:
        """聚合后昵称保持为第一条评论的昵称"""
        result = aggregate_users(simple_comments)
        assert result["u1"].nickname == "Alice"
        assert result["u2"].nickname == "Bob"

    def test_empty_input(self) -> None:
        """空评论列表返回空字典"""
        result = aggregate_users([])
        assert result == {}

    def test_short_comments_filtered(self, short_comments: List[Comment]) -> None:
        """短评论被过滤（默认 <5 字符）"""
        result = aggregate_users(short_comments)
        # Alice: 3条中1条有效（2条短被过滤）
        assert result["u1"].count == 1
        assert result["u1"].comments == ["正常评论内容"]
        # Bob: 2条中1条有效
        assert result["u2"].count == 1
        assert result["u2"].comments == ["另一条有效评论内容"]

    def test_min_comment_length_override(self, short_comments: List[Comment]) -> None:
        """自定义 min_comment_length 生效"""
        result = aggregate_users(short_comments, min_comment_length=3)
        # Alice: "短"(1) < 3, "hi"(2) < 3, 只剩1条有效
        # Bob: "OK"(2) < 3, 只剩1条有效
        assert result["u1"].count == 1
        assert result["u2"].count == 1

    def test_exclude_user_id(self, simple_comments: List[Comment]) -> None:
        """排除指定 user_id 的评论"""
        result = aggregate_users(simple_comments, exclude_user_id="u1")
        assert "u1" not in result
        assert len(result) == 2

    def test_exclude_empty_string(self, simple_comments: List[Comment]) -> None:
        """空排除字符串不排除任何用户"""
        result = aggregate_users(simple_comments, exclude_user_id="")
        assert len(result) == 3

    def test_all_comments_filtered(self, short_comments: List[Comment]) -> None:
        """所有评论都被过滤时返回空字典"""
        result = aggregate_users(short_comments, min_comment_length=999)
        assert result == {}

    def test_duplicate_nickname_users(self) -> None:
        """同昵称不同 user_id 各自独立聚合"""
        comments = [
            Comment(id="c1", user_id="u1", nickname="momo", content="第一条"),
            Comment(id="c2", user_id="u2", nickname="momo", content="第二条"),
            Comment(id="c3", user_id="u1", nickname="momo", content="第三条"),
        ]
        result = aggregate_users(comments)
        assert len(result) == 2
        assert result["u1"].count == 2
        assert result["u2"].count == 1


# ── 显示名获取 ────────────────────────────────────────────


class TestGetDisplayNames:
    """验证 get_display_names 映射"""

    def test_basic(self, simple_comments: List[Comment]) -> None:
        user_data = aggregate_users(simple_comments)
        names = get_display_names(user_data)
        assert names["u1"] == "Alice"
        assert names["u2"] == "Bob"
        assert names["u3"] == "Charlie"

    def test_empty_input(self) -> None:
        assert get_display_names({}) == {}

    def test_initial_empty_nickname(self) -> None:
        """user_id 作为 fallback，当 nickname 为空时"""
        user_data = {
            "u1": UserData(user_id="u1", nickname="", count=1, total_length=10),
        }
        names = get_display_names(user_data)
        assert names["u1"] != ""  # 至少不会空


# ── 权重计算 ──────────────────────────────────────────────


class TestCalculateWeights:
    """验证权重公式：sqrt(总字数) * log2(条数+1)"""

    def test_single_user_one_comment(self) -> None:
        """单用户单评论"""
        user_data = {
            "u1": UserData(user_id="u1", nickname="A", count=1, total_length=100),
        }
        weights = calculate_weights(user_data)
        expected = math.sqrt(100) * math.log2(2)  # sqrt(100)*log2(2) = 10*1 = 10
        assert abs(weights["u1"] - expected) < 1e-9

    def test_multiple_users(self) -> None:
        """多用户权重可比较"""
        user_data = {
            "u1": UserData(user_id="u1", nickname="A", count=2, total_length=200),
            "u2": UserData(user_id="u2", nickname="B", count=5, total_length=500),
        }
        weights = calculate_weights(user_data)
        # u2 评论数和字数都多，权重更高
        assert weights["u2"] > weights["u1"]

    def test_sqrt_formula_verification(self) -> None:
        """精确验证权重公式"""
        # 字数=100, 条数=3 → sqrt(100)*log2(4) = 10*2 = 20
        user_data = {
            "u1": UserData(user_id="u1", nickname="A", count=3, total_length=100),
        }
        weights = calculate_weights(user_data)
        assert abs(weights["u1"] - 20.0) < 1e-9

    def test_zero_count(self) -> None:
        """count=0 → log2(1)=0 → weight=0"""
        user_data = {
            "u1": UserData(user_id="u1", nickname="A", count=0, total_length=100),
        }
        weights = calculate_weights(user_data)
        assert weights["u1"] == 0.0

    def test_zero_length(self) -> None:
        """total_length=0 → sqrt(0)=0 → weight=0"""
        user_data = {
            "u1": UserData(user_id="u1", nickname="A", count=5, total_length=0),
        }
        weights = calculate_weights(user_data)
        assert weights["u1"] == 0.0

    def test_empty_input(self) -> None:
        assert calculate_weights({}) == {}

    def test_large_values(self) -> None:
        """大数据量不溢出"""
        user_data = {
            "u1": UserData(user_id="u1", nickname="A", count=10000, total_length=1000000),
        }
        weights = calculate_weights(user_data)
        assert weights["u1"] > 0
        assert math.isfinite(weights["u1"])

    def test_weight_monotonic(self) -> None:
        """字数固定时，评论数越多权重越高"""
        base_user = UserData(user_id="u", nickname="U", count=1, total_length=100)
        more_comments = UserData(user_id="u", nickname="U", count=10, total_length=100)

        w_base = calculate_weights({"u": base_user})["u"]
        w_more = calculate_weights({"u": more_comments})["u"]
        assert w_more > w_base


# ── 权重表构建 ────────────────────────────────────────────


class TestBuildWeightTable:
    """验证 build_weight_table 构建完整 WeightTable"""

    def test_single_entry(self) -> None:
        """单用户构建权重表"""
        user_data = {
            "u1": UserData(user_id="u1", nickname="Alice", count=2, total_length=100),
        }
        weights = calculate_weights(user_data)
        names = get_display_names(user_data)
        table = build_weight_table(weights, user_data, names)
        assert len(table.entries) == 1
        assert table.participant_count == 1
        assert table.total_weight > 0

    def test_multiple_entries(self, simple_comments: List[Comment]) -> None:
        """多用户构建权重表"""
        user_data = aggregate_users(simple_comments)
        weights = calculate_weights(user_data)
        names = get_display_names(user_data)
        table = build_weight_table(weights, user_data, names)
        assert len(table.entries) == 3

    def test_probability_sum_to_100(self, simple_comments: List[Comment]) -> None:
        """所有参与者的概率总和接近 100%"""
        user_data = aggregate_users(simple_comments)
        weights = calculate_weights(user_data)
        names = get_display_names(user_data)
        table = build_weight_table(weights, user_data, names)
        total = sum(e.probability_percent for e in table.entries)
        assert abs(total - 100.0) < 1.0  # 允许浮点误差

    def test_probability_ordering(self) -> None:
        """权重越高的条目概率越大"""
        user_data = {
            "u1": UserData(user_id="u1", nickname="Low", count=1, total_length=10),
            "u2": UserData(user_id="u2", nickname="High", count=5, total_length=500),
        }
        weights = calculate_weights(user_data)
        names = get_display_names(user_data)
        table = build_weight_table(weights, user_data, names)
        sorted_entries = table.sorted_by_weight_desc()
        assert sorted_entries[0].user_id == "u2"

    def test_empty_weights(self) -> None:
        """空权重返回空表"""
        table = build_weight_table({}, {}, {})
        assert len(table.entries) == 0
        assert table.participant_count == 0
        assert table.total_weight == 0.0

    def test_entry_fields_complete(self, simple_comments: List[Comment]) -> None:
        """每个 WeightEntry 字段完整"""
        user_data = aggregate_users(simple_comments)
        weights = calculate_weights(user_data)
        names = get_display_names(user_data)
        table = build_weight_table(weights, user_data, names)
        entry = table.entries[0]
        assert entry.user_id
        assert entry.display_name
        assert entry.nickname
        assert entry.comment_count > 0
        assert entry.total_length > 0
        assert entry.weight > 0
        assert entry.probability_percent > 0


# ── 重复昵称检测 ──────────────────────────────────────────


class TestGetDuplicateNicknames:
    """验证 get_duplicate_nicknames 检测"""

    def test_no_duplicates(self, simple_comments: List[Comment]) -> None:
        user_data = aggregate_users(simple_comments)
        dups = get_duplicate_nicknames(user_data)
        assert len(dups) == 0

    def test_some_duplicates(self) -> None:
        user_data = {
            "u1": UserData(user_id="u1", nickname="momo", count=5, total_length=100),
            "u2": UserData(user_id="u2", nickname="momo", count=3, total_length=60),
            "u3": UserData(user_id="u3", nickname="Alice", count=2, total_length=40),
        }
        dups = get_duplicate_nicknames(user_data)
        assert "momo" in dups
        assert dups["momo"] == 2
        assert "Alice" not in dups

    def test_all_unique(self) -> None:
        user_data = {
            "u1": UserData(user_id="u1", nickname="A", count=1, total_length=10),
            "u2": UserData(user_id="u2", nickname="B", count=1, total_length=10),
        }
        dups = get_duplicate_nicknames(user_data)
        assert dups == {}

    def test_empty_input(self) -> None:
        assert get_duplicate_nicknames({}) == {}
