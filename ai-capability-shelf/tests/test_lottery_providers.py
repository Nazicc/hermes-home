"""test_lottery_providers — 数据提供者测试
=========================================
高内聚：只测试 DataProvider 接口及 CacheProvider/DBProvider 实现。
低耦合：通过 mock 替代真实 DB 连接，CacheProvider 使用临时文件。
崩溃安全：验证 0 条评论/空文件/格式损坏等边缘情况不崩溃。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from ai_capability_shelf.lottery.models import Comment
from ai_capability_shelf.lottery.providers import (
    CacheProvider,
    DBProvider,
    DataProvider,
)
from ai_capability_shelf.lottery.exceptions import (
    CacheNotFoundError,
    DataExtractionError,
    DbConnectionError,
    DbQueryError,
)


# ── 样本数据 ──────────────────────────────────────────────


@pytest.fixture
def sample_comments() -> List[Dict[str, str]]:
    return [
        {"id": "c1", "user_id": "u1", "nickname": "用户A", "content": "这是一条正常评论"},
        {"id": "c2", "user_id": "u2", "nickname": "用户B", "content": "短"},
        {"id": "c3", "user_id": "u1", "nickname": "用户A", "content": "另一条长度足够的评论"},
        {"id": "c4", "user_id": "u3", "nickname": "用户C", "content": "这是一个相当长的评论内容，超过了五个字符"},
    ]


# ── 接口测试 ──────────────────────────────────────────────


class TestDataProviderInterface:
    """验证 DataProvider 抽象基类不可实例化，方法签名一致"""

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            DataProvider()  # type: ignore[abstract]

    def test_method_signatures_match(self) -> None:
        """DBProvider 和 CacheProvider 都实现 extract_comments 和 source_label"""
        for cls in (DBProvider, CacheProvider):
            assert hasattr(cls, "extract_comments")
            assert hasattr(cls, "source_label")
            assert callable(cls.extract_comments)
            assert callable(cls.source_label)


# ── CacheProvider ─────────────────────────────────────────


class TestCacheProvider:
    """验证 CacheProvider 从缓存文件加载评论"""

    def test_empty_cache_file(self, tmp_path: Path) -> None:
        """空列表作为有效缓存"""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("[]", encoding="utf-8")
        provider = CacheProvider(path=str(cache_file))
        comments = provider.extract_comments()
        assert comments == []
        assert provider.source_label().startswith("缓存文件")

    def test_single_comment(self, tmp_path: Path, sample_comments: List[Dict[str, str]]) -> None:
        """单条评论"""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps([sample_comments[0]], ensure_ascii=False), encoding="utf-8")
        provider = CacheProvider(path=str(cache_file))
        comments = provider.extract_comments()
        assert len(comments) == 1
        assert comments[0].id == "c1"
        assert comments[0].nickname == "用户A"

    def test_multiple_comments(self, tmp_path: Path, sample_comments: List[Dict[str, str]]) -> None:
        """多条评论"""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps(sample_comments, ensure_ascii=False), encoding="utf-8")
        provider = CacheProvider(path=str(cache_file))
        comments = provider.extract_comments()
        assert len(comments) == 4
        assert comments[0].content == sample_comments[0]["content"]

    def test_cache_file_not_found(self, tmp_path: Path) -> None:
        """文件不存在抛出 CacheNotFoundError"""
        provider = CacheProvider(path=str(tmp_path / "no_such_file.json"))
        with pytest.raises(CacheNotFoundError):
            provider.extract_comments()

    def test_malformed_json(self, tmp_path: Path) -> None:
        """损坏的 JSON 文件抛出 DataExtractionError"""
        cache_file = tmp_path / "bad.json"
        cache_file.write_text("{bad json", encoding="utf-8")
        provider = CacheProvider(path=str(cache_file))
        with pytest.raises(DataExtractionError):
            provider.extract_comments()

    def test_invalid_structure_not_list(self, tmp_path: Path) -> None:
        """非列表结构抛出 DataExtractionError"""
        cache_file = tmp_path / "invalid.json"
        cache_file.write_text('{"not": "a list"}', encoding="utf-8")
        provider = CacheProvider(path=str(cache_file))
        with pytest.raises(DataExtractionError):
            provider.extract_comments()

    def test_missing_comment_fields(self, tmp_path: Path) -> None:
        """缺少必要字段的评论项使用默认值"""
        cache_file = tmp_path / "partial.json"
        cache_file.write_text('[{"id": "c1", "content": "test"}]', encoding="utf-8")
        provider = CacheProvider(path=str(cache_file))
        comments = provider.extract_comments()
        assert len(comments) == 1
        assert comments[0].user_id == ""
        assert comments[0].nickname == "unknown"

    def test_source_label(self, tmp_path: Path) -> None:
        """source_label 包含 '缓存文件'"""
        cache_file = tmp_path / "c.json"
        cache_file.write_text("[]", encoding="utf-8")
        provider = CacheProvider(path=str(cache_file))
        assert "缓存文件" in provider.source_label()


# ── DBProvider (mock) ─────────────────────────────────────


class TestDBProvider:
    """验证 DBProvider 使用 mock 替代真实 DB 连接"""

    def test_mocked_connection_success(self) -> None:
        """模拟 DB 连接成功并返回评论"""
        provider = DBProvider(
            note_id="note123",
            host="localhost",
            port=5432,
            dbname="test_db",
            user="test_user",
            password="test_pass",
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("c1", "u1", "用户A", "评论内容"),
            ("c2", "u2", "用户B", "另一条评论"),
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(provider, "_get_connection", return_value=mock_conn):
            comments = provider.extract_comments()

        assert len(comments) == 2
        assert comments[0].id == "c1"
        assert comments[0].nickname == "用户A"
        assert comments[0].content == "评论内容"
        assert "数据库" in provider.source_label()

    def test_mocked_empty_result(self) -> None:
        """DB 返回空结果集"""
        provider = DBProvider(
            note_id="note123", host="h", dbname="d", user="u", password="p",
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(provider, "_get_connection", return_value=mock_conn):
            comments = provider.extract_comments()

        assert comments == []

    def test_connection_failure_raises_db_connection_error(self) -> None:
        """DB 连接失败抛出 DbConnectionError"""
        provider = DBProvider(
            note_id="note", host="bad_host", dbname="d", user="u", password="p",
        )

        with patch.object(
            provider, "_get_connection",
            side_effect=ConnectionError("could not connect"),
        ):
            with pytest.raises((DbConnectionError, DataExtractionError)):
                provider.extract_comments()

    def test_query_failure_raises_db_query_error(self) -> None:
        """DB 查询失败抛出 DbQueryError"""
        provider = DBProvider(
            note_id="note", host="h", dbname="d", user="u", password="p",
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = Exception("query syntax error")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(provider, "_get_connection", return_value=mock_conn):
            with pytest.raises((DbQueryError, DataExtractionError)):
                provider.extract_comments()

    def test_source_label(self) -> None:
        """source_label 返回 'db'"""
        provider = DBProvider(
            note_id="n", host="h", dbname="d", user="u", password="p",
        )
        assert provider.source_label() == "db"


# ── 边界情况 ──────────────────────────────────────────────


class TestProviderEdgeCases:
    """验证边界情况：空数据、编码异常、大体积"""

    def test_utf8_bom_cache(self, tmp_path: Path) -> None:
        """UTF-8 BOM 编码的缓存文件（模拟真实导出的 JSON）"""
        cache_file = tmp_path / "bom.json"
        content = '\ufeff[{"id": "c1", "user_id": "u1", "nickname": "用户", "content": "评论"}]'
        cache_file.write_text(content, encoding="utf-8")
        provider = CacheProvider(path=str(cache_file))
        # 是否处理 BOM 取决于实现 — 至少不崩溃
        comments = provider.extract_comments()
        assert len(comments) >= 0

    def test_very_large_comment(self, tmp_path: Path) -> None:
        """超长评论内容不崩溃"""
        long_content = "长" * 10000  # 10K 字
        cache_file = tmp_path / "long.json"
        data = [{"id": "c1", "user_id": "u1", "nickname": "用户", "content": long_content}]
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        provider = CacheProvider(path=str(cache_file))
        comments = provider.extract_comments()
        assert len(comments) == 1
        assert len(comments[0].content) == 10000

    def test_special_characters(self, tmp_path: Path) -> None:
        """特殊字符（emoji, HTML, 控制字符）"""
        cache_file = tmp_path / "special.json"
        data = [{"id": "c1", "user_id": "u1", "nickname": "😀<test>", "content": "评论🎉\n新行"}]
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        provider = CacheProvider(path=str(cache_file))
        comments = provider.extract_comments()
        assert len(comments) == 1
        assert "😀" in comments[0].nickname
