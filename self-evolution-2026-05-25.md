# Self-Evolution: Day 1 — ToolResult Integration Deep Dive

> Date: 2026-05-25 (Monday)
> Direction: ToolResult Integration into Execution Pipeline (P0)
> Cycle Day: 1/6

## Executive Summary

The `ToolResult` class (`agent/tool_result.py`) is fully built — well-designed data class with factory methods, serialization, 5-tuple backward compatibility — but has **zero integration points** in the actual execution pipeline (`run_agent.py`). Similarly, `SessionEventLog` (`agent/session_event_log.py`) with 11 event types is also completely unconnected. Today's investigation confirms the skill's assessment: the classes exist, the integration is the missing piece.

## Detailed Findings

### ✅ What Exists

#### ToolResult (`agent/tool_result.py`)

```
ToolResult(DataClass)
├── status: str                 # "success" | "error" | "cancelled"
├── output: str                 # The actual result content
├── error: str | None           # Error message if failed
├── duration: float | None      # Execution duration in seconds
├── metadata: dict | None       # Extra metadata
├── tool_call_id: str | None    # Tool call reference
├── tool_name: str | None       # Tool that produced this result
├── tool_args: str | None       # Serialized args
│
├── @classmethod from_output(output, ...)   # Create success result
├── @classmethod from_error(error, ...)     # Create error result  
├── @classmethod cancelled(...)             # Create cancelled result
├── to_message_dict() → dict     # Build tool message dict
├── to_dict() → dict             # Serialize to dict
├── from_dict(d) → ToolResult    # Deserialize from dict
├── from_message_dict(d) → ToolResult  # From message dict
└── to_5tuple() → tuple          # Backward compat: (content, name, is_error, duration, tool_call_id)
```

#### SessionEventLog (`agent/session_event_log.py`)

```
SessionEventLog
├── session_id: str
├── log_path: str (JSONL file)
│
├── emit(event_type, payload)    # Generic append
├── emit_tool_call(...)          # Tool call event
├── emit_tool_result(...)        # Tool result event
├── emit_brain_invoke(...)       # Brain API call event (⚠️ never called)
├── emit_brain_response(...)     # Brain response event (⚠️ never called)
├── emit_compression(...)        # Compression event (⚠️ never called)
├── replay() → list[dict]        # Full replay
├── get_events(offset=0, limit=None) → list[dict]  # Sliced read
├── count_events() → int
├── stats() → dict               # Event type counts
├── wake(session_id) → SessionEventLog  # 🟡 Stub: delegates to replay()
└── reconstruct_messages() → list[dict]  # 🔴 Does not exist
```

### ❌ What's Missing (Integration Points)

#### Pipeline Flow (run_agent.py)

```
_invoke_tool()
  └─ handle_function_call()          → returns: str (bare string)
     └─ registry.dispatch()           → returns: str (bare string)

_run_tool() (closure in concurrent path)
  └─ calls _invoke_tool()             → returns: str
  └─ _detect_tool_failure()           → checks: str
  └─ returns 5-tuple:                 → (name, args, str, duration, is_error)

Concurrent destructuring (line 8113):
  function_name, function_args, function_result, tool_duration, is_error = r

Tool message dict construction (line 8164-8168):
  tool_msg = {"role": "tool", "content": function_result, "tool_call_id": tc.id}

maybe_persist_tool_result() (line 8153):
  → input: str, output: str (handles oversized results, writes to sandbox)
  → NOT connected to ToolResult

Sequential path (line 8515):
  → Same bare-string pattern via _invoke_tool()
```

#### Key Gap: ToolResult exists but is never instantiated anywhere in `run_agent.py`

The 7 lines that would need changing:
1. `_run_tool()` — wrap result in `ToolResult.from_output()` or `.from_error()`
2. `_detect_tool_failure()` usage — could consume `ToolResult.status` instead of `str`
3. Destructuring (line 8113) — could unpack `ToolResult` instead of 5-tuple
4. Message dict (line 8164) — could use `tool_result.to_message_dict()`
5. `maybe_persist_tool_result()` — could accept `ToolResult.output` and attach metadata back
6. `enforce_turn_budget()` — works on message dicts, compatible either way
7. Sequential path — same changes mirrored

#### SessionEventLog Gap

The `SessionEventLog` has `emit_tool_call()`, `emit_tool_result()`, `emit_brain_invoke()`, `emit_brain_response()`, `emit_compression()` — but `run_agent.py` has:

- ❌ No `SessionEventLog` import
- ❌ No `SessionEventLog` instantiation
- ❌ No event emission anywhere (not even `tool_call`/`tool_result` events)
- ❌ No `wake()` mechanism (stub delegates to `replay()` — full-scan, no incremental recovery)
- ❌ No `reconstruct_messages()` method (needed for wake recovery)

### What Already Integrated (Sandbox Persistence)

The `tool_result_storage.py` layer IS integrated:

| Component | Status | Entry Points |
|-----------|--------|-------------|
| `maybe_persist_tool_result()` | ✅ Both paths (conc: 8153, seq: 8515) | Large results → sandbox file + preview |
| `enforce_turn_budget()` | ✅ Both paths (conc: 8175, seq: ~8520+) | Aggregate budget after all tools complete |
| `BudgetConfig` | ✅ Globally configured | Per-tool thresholds + turn budget |
| `_detect_tool_failure()` | ✅ Both paths (conc: ~8017, no seq check in viewed range) | Heuristic error detection on str |

## CMA vs Hermes: Updated Gap Table

| Dimension | CMA | Hermes (Current) | Effort |
|-----------|-----|------------------|--------|
| Tool Result Format | `execute() → Result{status, output, error, duration}` | Bare `str` (5-tuple destructured, no wrapping) | ★☆☆ |
| Tool Metadata | Structured fields per Result | `_tool_status`, `_tool_duration`, `_tool_error` in msg dict (added manually) | — |
| Tool Result Class | Built-in Result type | ✅ `ToolResult` exists but unused | ★☆☆ (integrate) |
| Session Event Log | append-only event stream | ✅ `SessionEventLog` exists but unused | ★★☆ (integrate) |
| Brain Events | `emitEvent("brain_invoke/response")` | ❌ No event emission | ★★☆ |
| Compression Events | `emitEvent("compression")` | ❌ No event emission | ★☆☆ |
| wake() Recovery | Rebuild from last event | 🟡 Stub only (delegates to `replay()`) | ★★☆ |
| getEvents(offset,limit) | Native API | ✅ Implemented in SessionEventLog | — |
| ToolResult 5-tuple compat | N/A | ✅ `to_5tuple()` ready for migration | — |

## Proposed Step 1 Implementation Plan (ToolResult Integration)

### Files to Modify

1. **`run_agent.py`** (lines 8000-8170, 8480-8550) — Concurrent & sequential tool execution paths
2. **`tools/tool_result_storage.py`** — `maybe_persist_tool_result()` signature to accept ToolResult
3. **`tools/registry.py`** — `dispatch()` return type (already str, could remain str — wrapping happens at caller)

### Implementation Steps

```
Step 1a: Modify _run_tool() (conc) to return ToolResult instead of 5-tuple
  └─ Call ToolResult.from_output() or ToolResult.from_error()
  └─ Use _detect_tool_failure() → set status
  └─ Return ToolResult directly
  └─ Changepoint: line ~8064-8022

Step 1b: Update destructuring (line 8113)
  └─ From: 5-tuple unpack
  └─ To:   tr = r; tr.tool_call_id = tc.id; tr.tool_name = name
  
Step 1c: Update message dict construction (line 8164-8168)
  └─ From: manual dict {role, content, tool_call_id}
  └─ To:   tr.to_message_dict()

Step 1d: Update maybe_persist_tool_result() call (line 8153)
  └─ Pass tr.output, attach persistence metadata back to tr

Step 1e: Mirror in sequential path (_execute_tool_calls_sequential, line 8484-8550)
  └─ Same pattern

Step 1f: Update _invoke_tool() return type annotation
  └─ str → ToolResult (or keep str and wrap in _run_tool)
```

### Risk Assessment

| Risk | Probability | Mitigation |
|------|------------|-----------|
| Backward compat with existing message dict consumers | Low | `to_message_dict()` produces identical schema to current manual dict |
| `_detect_tool_failure()` consumes str | Low | Keep same call; wrap in `_run_tool` after detection |
| `maybe_persist_tool_result()` signature change | Medium | Keep backward-compat `str` overload, add `ToolResult` overload |
| Gateway mode (non-CLI) uses different path | Medium | Verify `environments/agent_loop.py` also uses same pattern |
| SessionEventLog integration deferred | Low | Intentionally separate — Step 2 |

## Next Steps for Tomorrow (Day 2)

- Investigate `environments/agent_loop.py` for Gateway-mode tool execution patterns
- Locate exact API call boundaries for `brain_invoke`/`brain_response` event injection
- Check if `compress_messages()` is already using `SessionEventLog` anywhere
- Review `_detect_tool_failure()` implementation for integration with `ToolResult.status`

## Commands Verified

```bash
cd /Users/can/.hermes

# Module files exist:
python3 -c "import agent.tool_result; print(agent.tool_result.__file__)"     # ✅ /Users/can/.hermes/agent/tool_result.py
python3 -c "import agent.session_event_log; print(agent.session_event_log.__file__)"  # ✅ /Users/can/.hermes/agent/session_event_log.py

# No usage in run_agent.py:
grep -c "ToolResult" run_agent.py     # 0
grep -c "SessionEventLog" run_agent.py # 0

# maybe_persist_tool_result IS used:
grep -n "maybe_persist_tool_result" run_agent.py  # Lines 8153, 8515
grep -n "enforce_turn_budget" run_agent.py         # Lines 8175, ~8520+

# Sequential path mirrors concurrent:
grep -n "_execute_tool_calls_sequential" run_agent.py  # Line 8184
```

## References

- ToolResult class: `agent/tool_result.py` (24 lines, well-designed)
- SessionEventLog class: `agent/session_event_log.py` (132 lines, well-designed)
- Execution pipeline: `run_agent.py` (12,161 lines, central loop)
- Tool registry: `tools/registry.py` (dispatch returns str)
- Sandbox persistence: `tools/tool_result_storage.py` (226 lines)
