---
name: mem-search
description: "Three-layer memory search protocol for SimpleMem/MemPalace. Step 1: semantic index search → Step 2: timeline context → Step 3: fetch full entries. Covers session_search (long-term), search_memories (vector), sirchmunk (local files), and AMP-typed memories."
category: productivity
triggers: [search memory, find past sessions, recall previous work, look up a decision, check what was tried before, query memory, what did I learn, long-term memory, memory recall, remember, browse memory]
anti_triggers: [filesystem search, web search, current conversation, cache lookup, temporary note]
quality_redlines: ["Layer 1 (search) called first before Layer 3 (ask/get)", "AMP type filter used when known", "Session ID recorded before closing for future retrieval", "Results verified against actual memory store"]
---

# mem-search

Three-layer memory search protocol for discovering past sessions, decisions, and patterns via SimpleMem. Saves tokens by filtering before fetching full detail.

---

## Purpose

Use this skill when the user asks to search memory, find past sessions, recall previous work, look up a decision, check what was tried before, or query the agent's long-term memory. The three-layer protocol (semantic → timeline → full detail) ensures you retrieve relevant information without wasting context on irrelevant results.

---

## Why This Works

**1. The pyramid principle saves tokens.** Most queries match only a few relevant entries. Starting with a fast vector search (Layer 1) against the full index costs less than 10% of the tokens needed to load every entry's full text. You throw away 90% of irrelevant results before spending tokens on detail.

**2. Timeline ordering reveals causality.** Vector search returns by semantic similarity, which can miss the temporal relationship between entries. Layer 2 sorts results chronologically, letting you see cause and effect — the fix that followed the bug, the decision that followed the research.

**3. Type-aware filtering improves precision.** The AMP taxonomy (assessments, memories, procedures) lets you narrow search to the kind of information you need. Searching memory_type=error finds only failure patterns, not all the notes that mention an error in passing.

**4. Layered escalation avoids false negatives.** A query might fail at Layer 1 if the vector embedding doesn't capture the right semantics (e.g., synonyms or framing differences). Layer 2 uses different queries or broader search to catch what Layer 1 missed. Layer 3 loads full entries for manual scanning.

---

## Anti-Patterns

1. **Skipping Layer 1** — Jumping directly to ask() or reading memory export files wastes context on irrelevant sessions. Always start with search_memories or session_search at Layer 1, even if the query seems precise.

2. **Session Search on Active Session** — session_search works on closed (committed) sessions only. For the current conversation, use direct context or in-session variables. Calling it on an active session returns stale or empty results.

3. **Overusing observation Type** — The AMP taxonomy exists so you can query by type (memory_type=error). Defaulting to observation for every entry destroys this capability. Choose the most specific type — lesson for patterns, decision for rationale, error for bugs, procedure for workflows.

4. **Over-fetching Results** — Start with top_k=5. Large values on search_memories return low-relevance entries that dilute results. Increase only when the first batch returns nothing useful.

5. **No Tag Filtering** — Tags provide a lightweight grouping mechanism. Searching without tags when you know the relevant category returns extra noise. Combine semantic search with tag filters for precision.

6. **Forgetting to Record Key Findings** — If you find useful information through the search protocol but don't record it as a new memory (lesson/decision), you'll need to re-search later. Record what you find.

7. **Assuming Sirchmunk Replaces SimpleMem** — sirchmunk searches local files, not memory databases. For simple scripts and raw data, use sirchmunk. For structured memory with AMP taxonomy, use SimpleMem MCP tools.

8. **Chaining Too Deeply** — Following every potential lead recursively creates exponential blowup. After 2-3 hops without finding the answer, backtrack to Layer 1 with a refined query.

---

## Examples

**Good:** Recalling a past architectural decision using the three-layer protocol.

```
user: "Why did we choose pgvector over Qdrant?"
agent: Layer 1: session_search("chose pgvector over qdrant")
       Layer 2: get_session(session_id="sess_abc")
       Layer 3: ask("What was the rationale for choosing pgvector?")
# → "We chose pgvector because it integrates with our existing PostgreSQL instance, avoiding a separate vector DB infrastructure."
```

**Good:** Remembering a workaround found in a past debugging session.

```
user: "What was that workaround for the FastMCP timeout issue?"
agent: Layer 1: search_typed_memories("fastmcp timeout workaround", memory_type="lesson", limit=5)
       Layer 3 (skip L2 — high score): ask("What was the workaround for FastMCP timeout?")
# → "We increased the timeout parameter in MCP server config from 30s to 120s"
```

**Good:** Checking what was already tried when a previous approach failed.

```
user: "Did we already try deploying with Docker Compose?"
agent: Layer 1: session_search("docker compose deployment")
       Layer 2: get_session(session_id="sess_xyz")
       Layer 3: ask("What Docker Compose approach was tried and why did it fail?")
# → "Yes, Docker Compose was tried but failed because the PostgreSQL healthcheck timeout was too short."
```

**Bad:** Jumping directly to full entry fetch without narrowing scope.

```
user: "Find that thing about authentication"
agent: ask(query="What about authentication?", entry_ids=[])
# → Error: entry_ids required. Must call search_memories or session_search first.
```

**Bad:** Using the wrong layer for the wrong data source.

```
user: "What was the port number in the Docker Compose file?"
agent: session_search("docker compose port")
       # → No results (because it's in a local file, not in SimpleMem)
# → Better: Use sirchmunk to search the actual compose file on disk.
```

---

## When NOT to Use

- **For the current conversation context** — Already in the context window; use direct context rather than memory search.
- **For filesystem search** — Use sirchmunk, read_file, search_files, or terminal find/grep for local file content.
- **For real-time web search** — Use web search tools (duckduckgo-search, browser harness) for current information.
- **When memory MCP server is down and no export fallback exists** — Report the issue rather than hallucinating from stale data.
- **For ephemeral lookups** — If you only need to check something once, use direct context, not memory search.

---

## Cross-References

- **simplemem-integration** (skills/simplemem-integration/SKILL.md) — Build a custom FastMCP server that wraps SimpleMem for programmatic memory access.
- **simplemem-local-embedding** (skills/simplemem-local-embedding/SKILL.md) — Configure SimpleMem with a local embedding model to bypass external API calls.
- **simplemem-mcp** (skills/simplemem-mcp/SKILL.md) — Trade-offs, failure modes, and best practices for the SimpleMem MCP server.
- **amp-typed-memory** (skills/amp-typed-memory/SKILL.md) — Typed memory (lesson/checkpoint/reflection) for SimpleMem with the full AMP taxonomy.
- **hindsight** (skills/hindsight/SKILL.md) — Graph-based memory reasoning system that complements SimpleMem's vector search.
