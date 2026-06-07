"""
lottery.providers — 数据源抽象层
=================================
ABC + 两种实现（DB 直连 / JSON 缓存文件）。
高内聚：只做"数据提取"，不做聚合或权重计算。
低耦合：仅依赖 models.Comment，不引用其他 lottery 模块。
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import List, Optional

from ai_capability_shelf.lottery.models import Comment
from ai_capability_shelf.lottery.exceptions import (
    CacheNotFoundError,
    DbConnectionError,
    DbQueryError,
    DataExtractionError,
)


class DataProvider(ABC):
    """数据提供者抽象基类"""

    @abstractmethod
    def extract_comments(self) -> List[Comment]:
        """提取评论列表，每条评论含 user_id / nickname / content"""

    @abstractmethod
    def source_label(self) -> str:
        """数据源标签（用于输出显示）"""


# ── DB 直连提供者 ──────────────────────────────────────────


class DBProvider(DataProvider):
    """从 PostgreSQL 数据库提取评论"""

    def __init__(
        self,
        note_id: str,
        *,
        host: str = "",
        port: int = 5432,
        dbname: str = "xhs",
        user: str = "",
        password: str = "",
        connect_timeout: int = 10,
    ) -> None:
        self.note_id = note_id
        self._config = {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
            "connect_timeout": connect_timeout,
        }
        self._comments: Optional[List[Comment]] = None

    def source_label(self) -> str:
        return f"数据库直连 ({self._config['host']}:{self._config['port']}/{self._config['dbname']})"

    def extract_comments(self) -> List[Comment]:
        try:
            import psycopg2  # 延迟导入，仅在 DB 模式需要
        except ImportError:
            raise DataExtractionError(
                "缺少 psycopg2 库",
                detail="DB 模式需要安装 psycopg2-binary: pip install psycopg2-binary",
            )
        try:
            conn = psycopg2.connect(**self._config)
        except Exception as e:
            raise DbConnectionError(
                detail=f"数据库连接失败: {e}",
                context={"host": self._config["host"], "dbname": self._config["dbname"]},
            )

        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT raw_json FROM comments WHERE note_id = %s ORDER BY fetched_at DESC, id",
                (self.note_id,),
            )
            rows = cur.fetchall()
        except Exception as e:
            conn.close()
            raise DbQueryError(
                detail=f"评论查询失败: {e}",
                context={"note_id": self.note_id},
            )

        conn.close()
        self._comments = self._parse_db_rows(rows)
        return self._comments

    @staticmethod
    def _parse_db_rows(rows: list) -> List[Comment]:
        """解析 DB 返回的 JSON raw 行"""
        all_comments: List[Comment] = []
        seen_ids: set = set()

        for (raw_json,) in rows:
            raw = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
            comments = raw.get("data", {}).get("comments", [])

            for c in comments:
                cid = c.get("id", "")
                if cid in seen_ids:
                    continue
                seen_ids.add(cid)
                user_info = c.get("user_info", {})
                all_comments.append(
                    Comment(
                        id=cid,
                        user_id=user_info.get("user_id", ""),
                        nickname=user_info.get("nickname", "unknown"),
                        content=c.get("content", ""),
                    )
                )
                for sc in c.get("sub_comments", []):
                    scid = sc.get("id", "")
                    if scid in seen_ids:
                        continue
                    seen_ids.add(scid)
                    sc_user = sc.get("user_info", {})
                    all_comments.append(
                        Comment(
                            id=scid,
                            user_id=sc_user.get("user_id", ""),
                            nickname=sc_user.get("nickname", "unknown"),
                            content=sc.get("content", ""),
                        )
                    )
        return all_comments


# ── 缓存文件提供者 ─────────────────────────────────────────


class CacheProvider(DataProvider):
    """从 JSON 缓存文件提取评论"""

    def __init__(self, path: str) -> None:
        self.path = path
        self._comments: Optional[List[Comment]] = None

    def source_label(self) -> str:
        return f"缓存文件 ({os.path.basename(self.path)})"

    def extract_comments(self) -> List[Comment]:
        if not os.path.isfile(self.path):
            raise CacheNotFoundError(
                detail=f"缓存文件不存在: {self.path}",
            )
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise DataExtractionError(
                detail=f"缓存文件读取失败: {e}",
                context={"path": self.path},
            )
        self._comments = self._parse_cache_json(raw_data)
        return self._comments

    @staticmethod
    def _parse_cache_json(data: list) -> List[Comment]:
        """解析缓存 JSON（列表格式）为 Comment 对象"""
        return [
            Comment(
                id=c.get("id", ""),
                user_id=c.get("user_id", ""),
                nickname=c.get("nickname", "unknown"),
                content=c.get("content", ""),
            )
            for c in data
        ]
