#!/usr/bin/env python3
"""
SimpleMem MCP Server — Exposes SimpleMem long-term memory as MCP tools.

Architecture:
  Hermes Agent → MCP Client → simplemem_mcp.py (this server)
                                    ↓
                              SimpleMemSystem (LanceDB + embeddings)

Bypasses LLM-based memory builder entirely — uses embedding API directly
for both writes (encode → lance) and reads (encode → semantic search).

Uses SiliconFlow's BAAI/bge-m3 API (1024-dim) for embeddings.
Set SILICONFLOW_API_KEY in env or config.yaml.

Usage:
  python simplemem_mcp.py

Environment:
  SIMPLEMEM_DATA_DIR       — Data directory (default: ~/.hermes/simplemem-data)
  SILICONFLOW_API_KEY      — Required: SiliconFlow API key
  SILICONFLOW_BASE_URL     — Optional: API base URL (default: https://api.siliconflow.cn/v1)
  SILICONFLOW_EMBED_MODEL  — Optional: model name (default: BAAI/bge-m3)
"""

import asyncio
import datetime
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, List, Optional

import numpy as np
import requests

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

APP_NAME = "simplemem"
APP_VERSION = "2.0.0"  # switched to SiliconFlow API

DATA_DIR = os.environ.get("SIMPLEMEM_DATA_DIR", os.path.expanduser("~/.hermes/simplemem-data"))
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
EMBED_MODEL = os.environ.get("SILICONFLOW_EMBED_MODEL", "BAAI/bge-m3")
EMBED_DIMENSION = int(os.environ.get("SILICONFLOW_EMBED_DIMENSION", "1024"))

# Lazy system instance and direct vector store reference
_system = None
_vector_store = None


class SiliconFlowEmbedding:
    """Embedding model that calls SiliconFlow's OpenAI-compatible embedding API.

    Matches the interface expected by SimpleMem's VectorStore:
      - .dimension (int)
      - .encode_documents(documents: List[str]) -> np.ndarray
      - .encode_single(text: str, is_query: bool = False) -> np.ndarray
    """

    def __init__(
        self,
        api_key: str = SILICONFLOW_API_KEY,
        base_url: str = SILICONFLOW_BASE_URL,
        model: str = EMBED_MODEL,
        dimension: int = EMBED_DIMENSION,
    ):
        if not api_key:
            raise ValueError(
                "SILICONFLOW_API_KEY must be set. "
                "Add it to config.yaml under simplemem.env or to .env."
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimension = dimension
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        logger.info(
            f"SiliconFlowEmbedding initialized: model={model}, "
            f"dimension={dimension}, base_url={base_url}"
        )

    def encode(self, texts: List[str], is_query: bool = False) -> np.ndarray:
        """Encode a list of texts to dense vectors (batch)."""
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)

        # BAAI/bge-m3 uses instruction prefixes for query vs document encoding
        if is_query:
            prefixed = [f"Represent this sentence for searching relevant passages: {t}" for t in texts]
        else:
            prefixed = texts

        resp = self._session.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "input": prefixed},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        # Sort by index to preserve order
        embeddings = sorted(data["data"], key=lambda x: x["index"])
        vectors = np.array([e["embedding"] for e in embeddings], dtype=np.float32)

        # Normalize (bge-m3 outputs unnormalized by default via API)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        vectors = vectors / norms

        return vectors

    def encode_single(self, text: str, is_query: bool = False) -> np.ndarray:
        """Encode a single text."""
        return self.encode([text], is_query=is_query)[0]

    def encode_documents(self, documents: List[str]) -> np.ndarray:
        """Encode documents (no query prefix)."""
        return self.encode(documents, is_query=False)


def get_system():
    """Get or initialize SimpleMem system (lazy) with SiliconFlow embedding."""
    global _system, _vector_store
    if _system is None:
        from simplemem.system import SimpleMemSystem, VectorStore
        from simplemem.system import MemoryEntry  # noqa: F401 — needed for type

        Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

        # Create custom embedding model that uses SiliconFlow API
        embedding = SiliconFlowEmbedding()

        # Initialize VectorStore with our embedding model
        _vector_store = VectorStore(
            db_path=DATA_DIR,
            embedding_model=embedding,
        )

        _system = object()  # stub — we use _vector_store directly
        logger.info(
            f"SimpleMem (API-driven) initialized: data_dir={DATA_DIR}, "
            f"dim={embedding.dimension}"
        )
    return _system


def get_vector_store():
    """Get vector store reference for direct read/write operations."""
    get_system()  # ensure initialized
    return _vector_store


app = Server(APP_NAME)


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="search_memories",
            description="Semantic search over long-term memories. Returns top-k most relevant memory entries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "description": "Number of results (default 5)", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="add_memory",
            description="Add a new memory entry to long-term storage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Memory text to store"},
                    "metadata": {"type": "object", "description": "Optional metadata dict"},
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="session_search",
            description="Search long-term memories with synthesis — retrieves context and generates a summary answer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
                },
                "required": ["query"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    vs = get_vector_store()
    from simplemem.system import MemoryEntry

    if name == "search_memories":
        query = arguments["query"]
        top_k = arguments.get("top_k", 5)
        try:
            results = vs.semantic_search(query, top_k=top_k)
            if not results:
                return [TextContent(type="text", text="No relevant memories found.")]
            formatted = []
            for r in results:
                entry = {
                    "entry_id": r.entry_id,
                    "content": r.lossless_restatement,
                }
                if r.timestamp:
                    entry["timestamp"] = r.timestamp
                if r.topic:
                    entry["topic"] = r.topic
                if r.keywords:
                    entry["keywords"] = r.keywords
                formatted.append(entry)
            return [TextContent(type="text", text=json.dumps(formatted, ensure_ascii=False, indent=2))]
        except Exception as e:
            logger.error(f"search_memories error: {e}")
            try:
                all_mems = vs.get_all_entries()
                formatted = [{
                    "entry_id": m.entry_id,
                    "content": m.lossless_restatement[:200],
                } for m in all_mems[:top_k]]
                msg = f"[semantic_search failed: {e}]\n"
                msg += json.dumps(formatted, ensure_ascii=False, indent=2)
                return [TextContent(type="text", text=msg)]
            except Exception as e2:
                return [TextContent(type="text", text=f"Error: {e} (fallback: {e2})")]

    elif name == "add_memory":
        text = arguments["text"]
        try:
            now = datetime.datetime.now().isoformat()
            entry = MemoryEntry(
                entry_id=str(uuid.uuid4()),
                lossless_restatement=text,
                timestamp=now,
            )
            vs.add_entries([entry])
            logger.info(f"Memory added: {text[:60]}...")
            return [TextContent(type="text", text=f"Memory added: {text[:80]}...")]
        except Exception as e:
            logger.error(f"add_memory error: {e}")
            return [TextContent(type="text", text=f"Error: {e}")]

    elif name == "session_search":
        query = arguments["query"]
        limit = arguments.get("limit", 5)
        try:
            results = vs.semantic_search(query, top_k=limit)
            if not results:
                return [TextContent(type="text", text="No relevant memories found.")]
            formatted = []
            for r in results:
                entry = {
                    "entry_id": r.entry_id,
                    "content": r.lossless_restatement,
                }
                if r.timestamp:
                    entry["timestamp"] = r.timestamp
                if r.topic:
                    entry["topic"] = r.topic
                if r.keywords:
                    entry["keywords"] = r.keywords
                formatted.append(entry)
            return [TextContent(type="text", text=json.dumps(formatted, ensure_ascii=False, indent=2))]
        except Exception as e:
            logger.error(f"session_search error: {e}")
            try:
                all_mems = vs.get_all_entries()
                formatted = [{
                    "entry_id": m.entry_id,
                    "content": m.lossless_restatement[:200],
                } for m in all_mems[:limit]]
                msg = f"[search failed: {e}]\n"
                msg += json.dumps(formatted, ensure_ascii=False, indent=2)
                return [TextContent(type="text", text=msg)]
            except Exception as e2:
                return [TextContent(type="text", text=f"Error: {e} (fallback: {e2})")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
