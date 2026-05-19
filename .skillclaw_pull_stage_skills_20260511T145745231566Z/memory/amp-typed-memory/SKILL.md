---
name: amp-typed-memory
description: "Extends SimpleMem MCP with AMP-style typed memory (lesson/checkpoint/reflection) by encoding type metadata into the existing speaker/content JSON fields and adding type-filtered query tools. Use when you need structured, queryable memory types beyond plain text notes. NOT for tasks requiring a full AMP-RS installation or DSPy-based evolvers."
category: memory
---

---
name: amp-typed-memory
description: Extends SimpleMem MCP with AMP-style typed memory (lesson/checkpoint/reflection) by encoding type metadata into the existing speaker/content JSON fields and adding type-filtered query tools. Use when you need structured, queryable memory types beyond plain text notes. NOT for tasks requiring a full AMP-RS installation or DSPy-based evolvers.
---

# AMP-Style Typed Memory for SimpleMem MCP

## Concept
AMP-style typed memory adds semantic type labels (lesson, checkpoint, reflection) to SimpleMem's flat message store. The type system is encoded entirely in the existing `speaker` and `content` JSON fields — no new storage layer or backend required. This gives agents a way to query "show me only lessons" or "what was my last checkpoint" without scanning all messages.

## Memory Types

| Type         | Purpose                                          | Typical Lifespan |
|--------------|--------------------------------------------------|------------------|
| lesson       | Permanent knowledge, learnings, patterns         | Indefinite       |
| checkpoint   | State snapshot (files changed, decisions made)   | Session-to-session |
| reflection   | Meta-cognitive notes, agent self-assessment      | Session-to-session |
| state        | Key-value context for continuation (JSON blob)   | Session-to-session |

## SimpleMem MCP File Layout


~/.hermes/scripts/simplemem_mcp.py      # MCP server entrypoint + tool handlers
~/.hermes/scripts/simplemem/__init__.py
~/.hermes/scripts/simplemem/stores/memory_store.py  # LanceDB-backed store
~/.hermes/scripts/simplemem/stores/schema.py        # Schema definitions
~/.hermes/scripts/simplemem/retrievers/hybrid_retriever.py
~/.hermes/scripts/simplemem/utils.py
~/.hermes/scripts/simplemem/config.py


## Typed Memory Encoding

The typed memory system uses the `speaker` field as the type tag. The actual payload is stored in `content` as a JSON object.

**Speaker field format:**

typed:<type>   # e.g. typed:lesson, typed:checkpoint, typed:reflection


**Content field format:**

{
  "type": "lesson",
  "content": "<readable text>",
  "tags": ["python", "debugging"],
  "project": "myproject",
  "agent": "claude-code"
}


## MCP Tools for Typed Memory

These are the four typed-memory tools to add to `simplemem_mcp.py`. Implement them by calling `MemoryStore` methods with the typed speaker prefix.

### 1. store_typed_memory
Stores a typed message. Calls `memory_store.add_message()` with `speaker="typed:<type>"` and a JSON content blob.

**Parameters:**
- `memory_type` (str): lesson | checkpoint | reflection | state
- `content` (str): Human-readable text content
- `tags` (list[str], optional): Filter tags
- `project` (str, optional): Project identifier

**Returns:** `{"id": "...", "speaker": "typed:<type>", "status": "stored"}`

### 2. search_typed_memories
Queries typed memories with optional filters. Internally calls `memory_store.search_messages()` and post-filters by speaker prefix.

**Parameters:**
- `query` (str): Semantic search query
- `memory_type` (str, optional): Filter by type (lesson/checkpoint/reflection/state)
- `tags` (list[str], optional): Filter by tags (AND logic)
- `project` (str, optional): Filter by project
- `limit` (int, default=5): Max results

**Returns:** List of matching typed messages with decoded JSON content.

### 3. memory_status
Returns counts and recent messages per type. Useful for "what do I know?" prompts.

**Returns:** `{lesson: {count, recent}, checkpoint: {...}, reflection: {...}, state: {...}}`

### 4. get_recent_checkpoints
Returns the last N checkpoints. Useful for session resumption.

**Parameters:**
- `limit` (int, default=3)

**Returns:** List of checkpoint messages in reverse-chronological order.

## Implementation Pattern

In `simplemem_mcp.py`, add these as `@mcp.tool()` decorated async functions. Each one: (1) builds the typed speaker string, (2) encodes the content as JSON, (3) calls the existing `MemoryStore` methods. See `simplemem/stores/memory_store.py` for the `add_message()` and `search_messages()` APIs.

Example (checkpoint store):
python
import json

@mcp.tool()
async def store_typed_memory(
    memory_type: str,
    content: str,
    tags: list[str] = [],
    project: str = "default"
) -> dict:
    speaker = f"typed:{memory_type}"
    payload = {
        "type": memory_type,
        "content": content,
        "tags": tags,
        "project": project,
        "agent": os.environ.get("AGENT_NAME", "unknown")
    }
    msg_id = memory_store.add_message(speaker=speaker, content=json.dumps(payload))
    return {"id": msg_id, "speaker": speaker, "status": "stored"}


## When to Use

- **Use typed memory** when the task spans multiple sessions and the agent needs to persist structured state or learnings.
- **Use checkpoint** at the end of a complex task to capture what was done, what files changed, and any follow-up reminders.
- **Use lesson** when you discover a pattern, workaround, or domain-specific fact the agent should remember permanently.
- **Use reflection** when you want the agent to meta-assess its own performance.

## NOT For

- Tasks that already have a working AMP-RS installation (use that instead).
- Tasks requiring the DSPy-based evolver (requires `dspy-ai` and `amp-rs` toolchain, not present in this environment).
- Replacing the SimpleMem MCP server entirely — this skill extends it, not replaces it.

