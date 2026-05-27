---
name: simplemem-integration
description: "Build a custom FastMCP server that wraps SimpleMem and registers it as a Hermes MCP tool, so conversation memory survives across sessions with semantic search and reflection. Use when: building a custom MCP server from scratch, wrapping a Python library as an MCP tool for hermes, enabling cross-session memory, or the user asks to integrate simplemem with hermes. NOT for: simplemem already has a built-in MCP server (check simplemem-mcp skill first), one-off simplemem usage without hermes integration, or LanceDB storage issues (use simplestorage-adapter instead)."
category: general
---

## Architecture

openharness venv (`~/.openharness-venv/`)  →  simplemem + FastMCP
hermes-agent venv (`~/.hermes/hermes-agent/venv/`)  →  FastMCP (server-side)
hermes gateway  →  routes MCP stdio to simplemem MCP
config.yaml  →  registers simplemem in hermes mcp servers

**Two venvs matter:** hermes-agent's venv runs the gateway; simplemem lives in openharness venv.
When registering, use openharness venv's python as the `--command`.

## Prerequisites

bash
# Verify SimpleMem is installed and importable in the openharness venv
~/.openharness-venv/bin/python -c "from simplemem import SimpleMemSystem; print('OK')"

# Verify FastMCP is importable
~/.openharness-venv/bin/python -c "from mcp.server.fastmcp import FastMCP; print('OK')"

## Step 1: Create the FastMCP Script

Create `~/.hermes/scripts/simplemem_mcp.py`:

python
#!/usr/bin/env python3
"""
SimpleMem MCP Server — wraps SimpleMem as a FastMCP server for hermes.
Run with: python simplemem_mcp.py  (stdio transport, hermes manages lifecycle)
"""
import os
import sys
import json

# ── 1. Environment bootstrap ────────────────────────────────────────────────
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# ── 2. Import SimpleMem ───────────────────────────────────────────────────────
from simplemem import SimpleMemSystem

# ── 3. Monkey-patch HybridRetriever (avoids HuggingFace SSL blocks) ───────────
try:
    from simplemem.system import HybridRetriever
    _orig_init = HybridRetriever.__init__

    def _patched_init(self, *args, **kwargs):
        kwargs.setdefault("cache_dir", "/Users/can/.hermes/sirchmunk-data")
        _orig_init(self, *args, **kwargs)

    HybridRetriever.__init__ = _patched_init
except ImportError:
    pass  # HybridRetriever not in this version

# ── 4. Lazy singleton system instance ───────────────────────────────────────
_SYSTEM_CACHE = {}

def _get_system():
    pid = os.getpid()
    if pid not in _SYSTEM_CACHE:
        _SYSTEM_CACHE[pid] = SimpleMemSystem()
    return _SYSTEM_CACHE[pid]

# ── 5. FastMCP server ─────────────────────────────────────────────────────────
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="simplemem",
    instructions="Persistent conversation memory with semantic search and reflection. "
                 "Add dialogues, search history, and trigger reflection agents."
)

# ── 6. Define MCP tools ───────────────────────────────────────────────────────

@mcp.tool()
def add_dialogue(speaker: str, content: str, timestamp: str | None = None) -> str:
    """Add a single dialogue turn to memory.
    Args:
        speaker: 'user' or 'assistant'
        content: the text content
        timestamp: optional ISO timestamp (auto-generated if omitted)
    """
    sys = _get_system()
    sys.add_dialogue(speaker=str(speaker), content=str(content), timestamp=timestamp)
    return f"Added: [{speaker}] {content[:80]}{'...' if len(content) > 80 else ''}"

@mcp.tool()
def add_dialogues(dialogues_json: str) -> str:
    """Bulk-add dialogue turns from a JSON array.
    Args:
        dialogues_json: JSON string like '[{"speaker":"user","content":"..."}, ...]'
    Returns:
        Count of dialogues added
    """
    sys = _get_system()
    try:
        items = json.loads(dialogues_json)
    except json.JSONDecodeError as e:
        return f"JSON parse error: {e}"

    if not isinstance(items, list):
        return f"Expected JSON array, got {type(items).__name__}"

    count = 0
    for item in items:
        if not isinstance(item, dict) or "speaker" not in item or "content" not in item:
            return f"Invalid item (must be {{speaker, content, timestamp?}}): {item}"
        sys.add_dialogue(
            speaker=str(item["speaker"]),
            content=str(item["content"]),
            timestamp=str(item["timestamp"]) if item.get("timestamp") else None,
        )
        count += 1
    return f"Added {count} dialogue(s)."

@mcp.tool()
def finalize() -> str:
    """Flush buffered dialogues and compute their vector embeddings.
    REQUIRED before calling ask() or search_memories().
    """
    sys = _get_system()
    if hasattr(sys, "finalize"):
        sys.finalize()
    return "Memory finalized and indexed."

@mcp.tool()
def ask(question: str, top_k: int = 5) -> str:
    """Answer a question using the full memory store (semantic + BM25 + reflection).
    Args:
        question: the question to answer
        top_k: number of results to consider (default 5)
    Must call finalize() first if any add_dialogue() calls were made since the last ask().
    """
    sys = _get_system()
    return str(sys.ask(question, top_k=top_k))

@mcp.tool()
def search_memories(query: str, top_k: int = 5) -> str:
    """Retrieve top-K semantically relevant memories without LLM reflection.
    Args:
        query: natural-language query
        top_k: number of results to return (default 5)
    Returns:
        JSON array of matched memories
    """
    sys = _get_system()
    results = sys.search_memories(query=query, top_k=top_k)
    if not results:
        return "No relevant memories found."
    return json.dumps(results, indent=2, ensure_ascii=False)

@mcp.tool()
def get_all_memories(limit: int = 100) -> str:
    """Get recent memories in chronological order.
    Args:
        limit: max number of entries (default 100)
    """
    sys = _get_system()
    rows = sys.get_all_memories(limit=limit)
    if not rows:
        return "No memories found."
    lines = [f"[{r['dialogue_id']}] {r['speaker']}: {r['content']}" for r in rows]
    return "\n".join(lines)

@mcp.tool()
def clear_memories(confirm: str = "no") -> str:
    """Permanently delete all stored memories. Requires confirm='yes'."""
    if confirm.lower() != "yes":
        return "Aborted. Pass confirm='yes' to clear."
    sys = _get_system()
    sys.clear_memories()
    return "All memories cleared."

# ── 7. Start stdio server ─────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")


## Step 2: Critical API Notes

### FastMCP `__init__()` Constraints

**Correct `FastMCP.__init__()` signature:**
bash
~/.hermes/hermes-agent/venv/bin/python -c "from mcp.server.fastmcp import FastMCP; import inspect; print(inspect.signature(FastMCP.__init__))"


| ❌ Wrong | ✅ Correct | Reason |
|---|---|---|
| `description="..."` | `instructions="..."` | No `description` kwarg; use `instructions` for LLM-facing text |
| `dependencies=["pkg"]` | Omit | Dependencies handled by venv environment |
| `mcp.run()` without args | `mcp.run(transport="stdio")` | hermes communicates via stdio |

### SimpleMemSystem API

bash
~/.openharness-venv/bin/python -c "
from simplemem import SimpleMemSystem; import inspect
sys = SimpleMemSystem()
print(inspect.signature(sys.add_dialogue))
print('---')
print(inspect.signature(sys.search_memories))
print('---')
print(inspect.signature(sys.finalize))
"


- `add_dialogue(self, speaker: str, content: str, timestamp: Optional[str] = None)` — dialogue_id is auto-generated
- Do NOT construct `Dialogue` Pydantic objects directly (requires `dialogue_id`)
- Always call `sys.finalize()` before `sys.ask()` to flush embeddings to the vector DB

## Step 3: Verify the Script

bash
# Syntax + import check
~/.hermes/hermes-agent/venv/bin/python -c "import ast; ast.parse(open('/Users/can/.hermes/scripts/simplemem_mcp.py').read()); print('SYNTAX_OK')"

# Quick integration test
~/.hermes/hermes-agent/venv/bin/python -c "import sys; sys.path.insert(0, '/Users/can/.hermes/scripts/simplemem_mcp.py')"


## Step 4: Register with hermes

bash
hermes mcp add simplemem \
  --command /Users/can/.openharness-venv/bin/python \
  --args /Users/can/.hermes/scripts/simplemem_mcp.py


Interactive confirmation will be requested. Pipe `echo "y"` if needed:

bash
hermes mcp remove simplemem 2>/dev/null
hermes mcp add simplemem --command /Users/can/.openharness-venv/bin/python --args /Users/can/.hermes/scripts/simplemem_mcp.py


Add to `~/.hermes/config.yaml`:

yaml
mcp:
  simplemem:
    command: /Users/can/.openharness-venv/bin/python
    args:
      - /Users/can/.hermes/scripts/simplemem_mcp.py
    enabled: true


Verify status:

bash
hermes mcp list
hermes mcp test simplemem


## Step 5: Auto-Start with hermes gateway

The hermes gateway launchd plist (`ai.hermes.gateway.plist`) handles `RunAtLoad=true` and `KeepAlive`. Since the simplemem MCP server is registered in `~/.hermes/config.yaml` under `mcp:`, it automatically starts whenever hermes does — no separate launchd plist needed.

If hermes is not running:

bash
launchctl load ~/Library/LaunchAgents/ai.hermes.gateway.plist


## Step 6: Available Tools (7 total)

| Tool | Purpose | When to use |
|------|---------|-------------|
| `add_dialogue` | Add single dialogue turn | After each user/assistant turn |
| `add_dialogues` | Bulk add from JSON array | Bulk ingest (e.g., prior conversation summary) |
| `finalize` | Flush to vector database | Before `ask()` — computes vector embeddings |
| `ask` | Semantic Q&A over memory | Query memory with LLM reflection |
| `search_memories` | Semantic search | Retrieve relevant past context |
| `get_all_memories` | Retrieve all memories | Timeline dump |
| `clear_memories` | Delete all memories | Wipe for new session (requires confirm='yes') |

### Example Agent Flow


user: 帮我写一个 REST API
-> add_dialogue(speaker="user", content="帮我写一个 REST API")
-> [code generation]
-> add_dialogue(speaker="assistant", content="Here is a REST API...")
-> finalize()

user: 上次我让你做什么？
-> ask(question="上次我让你做什么？")


## Validation Checklist

- [ ] FastMCP `__init__` uses `name` + `instructions` (not `description`/`dependencies`)
- [ ] `mcp.run(transport="stdio")` is called
- [ ] `SimpleMemSystem.add_dialogue()` called directly (no `Dialogue` object instantiation)
- [ ] Env vars loaded from `~/.hermes/.env` before library imports
- [ ] Registered via `hermes mcp add` and appears in `hermes mcp list`
- [ ] Config entry added to `~/.hermes/config.yaml` under `mcp:`
- [ ] Syntax validated: `python -m py_compile script.py`
- [ ] Tool discovery works: `hermes mcp list` shows 7 tools

## Practical Gotchas

| Issue | Cause | Fix |
|---|---|---|
| `TypeError: FastMCP.__init__() got unexpected keyword argument 'description'` | `description` is not a valid FastMCP kwarg | Use `instructions` instead |
| `Dialogue` pydantic validation fails with `dialogue_id required` | `Dialogue` model requires auto-generated ID | Call `sys.add_dialogue()` directly instead of constructing `Dialogue` objects |
| Import fails: `ModuleNotFoundError: simplemem` | wrong venv activated | Use openharness venv python, not hermes-agent venv |
| MCP connects but tools don't appear | hermes gateway still running old registration | Start a new hermes session to pick up config changes |
| HuggingFace SSL errors during embedding | network restrictions | Monkey-patch `HybridRetriever.__init__` to set `cache_dir` |
| `hermes mcp list` doesn't show server | registration not persisted | Add entry to `~/.hermes/config.yaml` |

## Related Skills

- `simplemem-mcp` — Check if simplemem already has a built-in MCP server before building your own
- `simplestorage-adapter` — For LanceDB installation issues or switching to PostgreSQL/pgvector
- `simplemem-local-embedding` — Configure local embedding models to avoid HuggingFace SSL blocks
- `mcp-debugging` — General MCP server debugging if simplemem MCP fails
