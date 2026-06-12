#!/usr/bin/env python3
"""
memU MCP Server — 7×24 自进化记忆系统

Provides tools for long-term memory storage, semantic retrieval,
and self-evolution via memu-py + PostgreSQL pgvector + SiliconFlow embedding.

MCP tools:
  - memu_memorize: Store text content as a memory item
  - memu_retrieve: Semantic search over stored memories
  - memu_list_memories: List/query stored memory items
  - memu_evolution_status: Health & stats of memU storage
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

# Ensure memu-venv is importable
sys.path.insert(0, os.path.expanduser("~/.hermes/memu-venv/lib/python3.14/site-packages"))

from mcp.server.fastmcp import FastMCP
from memu.app.service import MemoryService
from memu.app.settings import (
    BlobConfig,
    DatabaseConfig,
    MetadataStoreConfig,
    VectorIndexConfig,
    LLMConfig,
    LLMProfilesConfig,
    MemorizeConfig,
    RetrieveConfig,
    UserConfig,
)

# ── Configuration ─────────────────────────────────────────────────────────────
# Read env vars from .env
def _load_env() -> dict[str, str]:
    env = {}
    env_path = os.path.expanduser("~/.hermes/.env")
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k] = v
    return env

_env = _load_env()

DEEPSEEK_API_KEY = _env.get("DEEPSEEK_API_KEY", "")
SILICONFLOW_API_KEY = _env.get("SILICONFLOW_API_KEY", "")

def _read_dsn_from_config() -> str:
    """Read MEMU_DATABASE_URL directly from config.yaml (raw file I/O).
    This bypasses Hermes's env-var masking which can inject *** into
    the subprocess environment."""
    cfg = os.path.expanduser("~/.hermes/config.yaml")
    try:
        with open(cfg, "rb") as f:
            for line in f:
                if b"MEMU_DATABASE_URL:" in line:
                    raw = line.decode("utf-8").strip()
                    idx = raw.find("MEMU_DATABASE_URL:")
                    val = raw[idx + len("MEMU_DATABASE_URL:"):].strip().strip("\"'")
                    if val:
                        return val
    except OSError:
        pass
    return os.environ.get("MEMU_DATABASE_URL", "")

_RAW_DSN = _read_dsn_from_config()

# URL-encode password in DSN to protect special chars (@, :, etc.)
# Standard libpq / psycopg2 DSN parsing splits at LAST @ in netloc;
# we split at FIRST @ for correct user:password boundary.
_SCHEME = "postgresql://"
DATABASE_DSN = _RAW_DSN
if DATABASE_DSN.startswith(_SCHEME):
    _after_scheme = DATABASE_DSN[len(_SCHEME):]
    _first_at = _after_scheme.find('@')
    if _first_at > 0:
        _userinfo = _after_scheme[:_first_at]
        _rest = _after_scheme[_first_at + 1:]
        _colon = _userinfo.find(':')
        if _colon > 0:
            import urllib.parse as _up
            _user = _userinfo[:_colon]
            _pw = _userinfo[_colon + 1:]
            DATABASE_DSN = f"{_SCHEME}{_user}:{_up.quote(_pw, safe='')}@{_rest}"

RESOURCES_DIR = os.path.expanduser("~/.hermes/memu_data/resources")

# Build configuration objects
database_config = DatabaseConfig(
    metadata_store=MetadataStoreConfig(
        provider="postgres",
        dsn=DATABASE_DSN,
    ),
    vector_index=VectorIndexConfig(
        provider="pgvector",
        dsn=DATABASE_DSN,
    ),
)

blob_config = BlobConfig(
    provider="local",
    resources_dir=RESOURCES_DIR,
)

llm_profiles = LLMProfilesConfig(
    root={
        "default": LLMConfig(
            provider="deepseek",
            base_url="https://api.deepseek.com/v1",
            api_key=DEEPSEEK_API_KEY,
            chat_model="deepseek-chat",
            client_backend="sdk",
            embed_model="BAAI/bge-m3",
            embed_batch_size=5,
        ),
        "embedding": LLMConfig(
            provider="siliconflow",
            base_url="https://api.siliconflow.cn/v1",
            api_key=SILICONFLOW_API_KEY,
            chat_model="deepseek-chat",
            client_backend="sdk",
            embed_model="BAAI/bge-m3",
            embed_batch_size=5,
        ),
    }
)

memorize_config = MemorizeConfig(
    category_assign_threshold=0.25,
)

retrieve_config = RetrieveConfig(
    method="rag",
    route_intention=True,
)

user_config = UserConfig()

# ── MCP Server ────────────────────────────────────────────────────────────────
mcp = FastMCP(
    name="memU-MCP",
    instructions="memU 自进化记忆系统 — 长期记忆存储、语义检索、自动聚类",
)

_service: MemoryService | None = None


async def _get_service() -> MemoryService:
    """Lazy singleton for MemoryService."""
    global _service
    if _service is None:
        import traceback as _tb
        try:
            _service = MemoryService(
                llm_profiles=llm_profiles,
                blob_config=blob_config,
                database_config=database_config,
                memorize_config=memorize_config,
                retrieve_config=retrieve_config,
                user_config=user_config,
            )
        except Exception as _e:
            _msg = f"[CRASH] _get_service() failed: {_e}\n{_tb.format_exc()}"
            import sys as _sys
            _sys.stderr.write(_msg + "\n")
            _sys.stderr.flush()
            open("/tmp/memu_crash.log", "a").write(_msg + "\n")
            raise
    return _service


@mcp.tool(description="Store a piece of text content as a memory item.")
async def memu_memorize(
    text: str,
    memory_type: str = "knowledge",
    categories: list[str] | None = None,
) -> dict:
    """Store a piece of text content as a memory item.

    Args:
        text: The text content to remember (can be long-form).
        memory_type: Type of memory — 'knowledge', 'experience', 'profile',
            'behavior', 'event', or 'reflection'. Default: 'knowledge'.
        categories: List of categories to assign (e.g., ['work_life', 'knowledge']).
            If omitted, auto-categorization is used.
    Returns:
        Dict with memory_id, status, and timestamp.
    """
    svc = await _get_service()
    if categories is None:
        categories = ["knowledge"]

    result = await svc.create_memory_item(
        memory_type=memory_type,
        memory_content=text,
        memory_categories=categories,
        user={"user_id": "hermes-agent"},
    )
    return {
        "status": "ok",
        "memory_id": result.get("item_id", result.get("id", "unknown")),
        "memory_type": memory_type,
        "categories": categories,
        "content_preview": text[:120] + ("..." if len(text) > 120 else ""),
    }


@mcp.tool(description="Semantic search over stored memories.")
async def memu_retrieve(
    query: str,
    top_k: int = 5,
) -> dict:  # Returns dict with query/total/memories
    """Semantic search over stored memories.

    Args:
        query: Natural language query to search for.
        top_k: Maximum number of results to return (1-20). Default: 5.
    Returns:
        List of memory items ranked by relevance.
    """
    svc = await _get_service()
    result = await svc.retrieve(
        queries=[{"role": "user", "content": query}],
    )

    memories = []
    # Parse workflow result for memory items
    raw_items = result.get("items", []) or []
    for item in raw_items[:top_k]:
        memories.append({
            "id": item.get("id", ""),
            "content": item.get("content", ""),
            "memory_type": item.get("memory_type", ""),
            "categories": item.get("categories", []),
            "score": item.get("score", 0.0),
            "created_at": item.get("created_at", ""),
        })

    return {
        "query": query,
        "total": len(memories),
        "memories": memories,
    }


@mcp.tool(description="List stored memory items with optional type filter.")
async def memu_list_memories(
    limit: int = 20,
    offset: int = 0,
    memory_type: str | None = None,
) -> dict:
    """List stored memory items with optional type filter.

    Args:
        limit: Max items to return (1-100). Default: 20.
        offset: Pagination offset. Default: 0.
        memory_type: Optional filter by memory type
            ('knowledge', 'experience', 'profile', 'behavior', 'event', 'reflection').
    Returns:
        Dict with total count and list of memory items.
    """
    svc = await _get_service()
    where = {}
    if memory_type:
        where["memory_type"] = memory_type
    result = await svc.list_memory_items(where=where or None)
    all_items = result.get("items", []) if isinstance(result, dict) else result
    items = all_items[offset:offset + limit]
    return {
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": i.get("id", ""),
                "memory_type": i.get("memory_type", ""),
                "content_preview": (i.get("content", "") or "")[:200],
                "categories": i.get("categories", []),
                "created_at": i.get("created_at", ""),
            }
            for i in items
        ],
    }


@mcp.tool(description="Check memU health and evolution status.")
async def memu_evolution_status() -> dict:
    """Check memU health and evolution status.

    Returns:
        Dict with database connectivity, categories count, and memory stats.
    """
    svc = await _get_service()
    try:
        items = await svc.list_memory_items()
        categories_result = await svc.list_memory_categories()
        categories_list = categories_result.get("categories", []) if isinstance(categories_result, dict) else (categories_result if isinstance(categories_result, list) else [])
        total = len(items.get("items", []))
        return {
            "status": "healthy",
            "database": "postgresql+pgvector",
            "categories_count": len(categories_list),
            "categories": categories_list,
            "total_items": total,
            "embedding_model": "BAAI/bge-m3 (1024d, SiliconFlow)",
            "chat_model": "deepseek-chat (DeepSeek native)",
            "total_items_estimate": "query via memu_list_memories for full count",
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


def main():
    print("Starting memU MCP server...", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
