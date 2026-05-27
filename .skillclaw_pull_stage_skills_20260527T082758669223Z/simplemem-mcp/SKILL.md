---
name: simplemem-mcp
description: "Documents the reverse-engineered SimpleMem MCP server API and known fixes. Use when you need to query, inspect, or troubleshoot the SimpleMem long-term memory system. NOT for general vector database usage, unrelated MCP servers, or when the simplemem-mcp skill already exists and is working."
category: general
---

# SimpleMem MCP — Usage Guide

## Overview
SimpleMem is a local long-term memory MCP server using LanceDB + SiliconFlow. It exposes tools for semantic search, Q&A, and memory inspection.

## Architecture


User Query
    ↓
~/.hermes/scripts/simplemem_mcp.py  (MCP server, raw JSON-RPC over stdio)
    ↓
SimpleMemSystem  (LanceDB + SiliconFlow embeddings)
    ↓
~/.hermes/MEMORY.md  (append-only memory log)


SimpleMem is a local long-term memory system using:
- **LanceDB** for local vector storage (`~/.hermes/simplemem/lancedb/`)
- **SiliconFlow API** for embeddings and chat synthesis
- **stdin/stdout MCP protocol** — hermes-agent connects via `mcp.sirchmunk.com` remote proxy

## Configuration

The MCP server reads `~/.hermes/simplemem/config.yaml`:

yaml
llm:
  model_id: "MiniMax/MiniMax-Text-01"  # embedding + chat model
vector_store:
  path: "~/.hermes/simplemem/lancedb/"
  dimension: 1024


## SimpleMemSystem Class

python
class SimpleMemSystem:
    def __init__(self, config_path: str = "config.yaml"):
        # Loads config.yaml — does NOT accept embedding_model parameter
        self.cfg = ...
        self.vector_store = LanceDBVectorStore(...)
        self.llm = SiliconFlowLLM(...)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        # Semantic search — embeds query via SiliconFlow, searches LanceDB
        # Returns list of {id, text, score, metadata}

    def synthesize(self, messages: list[dict]) -> str:
        # Takes conversation messages, retrieves relevant context,
        # synthesizes response via SiliconFlow chat completion

    def add_entry(self, entry: dict) -> None:
        # Add memory entry to LanceDB


## MCP Tools

### session_search — long-term semantic memory recall


{"tool": "session_search", "args": {"query": "user preferences", "limit": 5}}


### search_memories — vector similarity search


{"tool": "search_memories", "args": {"query": "python async best practices", "limit": 3}}


### print_memories — inspect memory log

Prints all entries from MEMORY.md, optionally filtered.

## Direct Python Usage

python
import sys
sys.path.insert(0, "/Users/can/.hermes/scripts")
from simplemem_mcp import SimpleMemSystem

mem = SimpleMemSystem("/Users/can/.hermes/simplemem/config.yaml")

# Semantic search
results = mem.search("docker compose restart policy", top_k=3)

# LLM synthesis
response = mem.synthesize([{"role": "user", "content": "explain docker restart"}])


## Known Fixes

### `SimpleMemSystem.__init__() got an unexpected keyword argument 'embedding_model'`

**Cause**: Old code passes `embedding_model` to `SimpleMemSystem.__init__` — this parameter does NOT exist. The model is determined by `config.yaml`.

**Fix**: Remove `embedding_model` from all `SimpleMemSystem()` calls. Set the model in `config.yaml`:
yaml
llm:
  model_id: "MiniMax/MiniMax-Text-01"


### `AttributeError: 'SimpleMemSystem' object has no attribute 'vector_store'` / `'ask'`

**Cause**: The old API documented `sys.vector_store.semantic_search` and `sys.ask`. These do NOT exist.

**Fix**: Use `mem.search(query)` for vector similarity and `mem.synthesize(messages)` for LLM synthesis.

### MCP tool returns 500 with no error message

**Cause**: SimpleMem server is down, unreachable, or the LanceDB index is corrupted.

**Fix**: Check if the simplemem MCP server is running (`ps aux | grep simplemem`). If not, restart it. If LanceDB is corrupted, rebuild the index.

## What NOT to do

- Do NOT pass `embedding_model` to SimpleMemSystem() — it will raise TypeError
- Do NOT call `sys.vector_store.semantic_search()` — that attribute does not exist
- Do NOT call `sys.ask()` — use `mem.synthesize(messages)` instead
- Do NOT assume SimpleMem MCP runs on HTTP — it uses stdio with JSON-RPC 2.0 protocol

## Memory Log

Append-only log at `~/.hermes/MEMORY.md`. Format:

markdown
## [YYYY-MM-DD] Context topic

Content here...


## Limitations

- No built-in deduplication — repeated inserts produce duplicate chunks
- LanceDB path must be writable
- SiliconFlow API key required for embeddings
- SimpleMem MCP uses stdio protocol, not HTTP

