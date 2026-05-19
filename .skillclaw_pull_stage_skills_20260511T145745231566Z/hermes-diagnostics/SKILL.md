---
name: hermes-diagnostics
description: "Query Hermes Agent's internal SQLite state.db for session metrics, token usage, compression events, and error analysis. Use when generating health reports, debugging issues, or analyzing usage patterns. Also useful for token cost estimation, detecting context overflow risk, and identifying recurring errors. NOT for: exploring session content (use session JSON files), or for reliable token tracking (tokens are often all-zero since the provider doesn't report usage back to Hermes)."
category: general
---

## Data Source

**SQLite DB**: `~/.hermes/state.db`

> **Key insight**: Session JSON files in `~/.hermes/sessions/` contain message arrays but often lack reliable `turn_count`, `input_tokens`, `output_tokens`, compression flags, or end reasons. For quantitative analysis always query `state.db`. Session JSON is appropriate only when you need actual message content of a specific session.

**Secondary database**: `~/.hermes/evolution.db` — for skill evolution metrics.

## Database Schema

> ⚠️ **Always query the actual schema first** — the schema has changed across Hermes versions. Run:
> sql
> SELECT sql FROM sqlite_master WHERE type='table' AND name IN ('sessions','messages');
> 
> to get the authoritative column list for your deployment.

### `sessions` table

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key (e.g., `20260423_234411_eb7a01`) |
| source | TEXT | Session source (`feishu`, `cron`, `cli`, `tui`, `cron_<job_id>`, etc.) |
| user_id | TEXT | User identifier |
| model | TEXT | Model name (e.g., `MiniMax-M2.7`, `claude-4-sonnet-20250514`) |
| model_config | TEXT | JSON string with model config |
| system_prompt | TEXT | System prompt used |
| parent_session_id | TEXT | Parent session ID if continuation |
| started_at | REAL | Unix epoch timestamp (UTC) |
| ended_at | REAL | Unix epoch when session ended (nullable) |
| end_reason | TEXT | `stop`, `max_iterations`, `error`, `timeout`, `idle_timeout`, `compression`, `context_overflow`, `manual`, `cron_complete`, `done`, `success`, `compression`, etc. |
| message_count | INTEGER | Total messages in session (all roles, not just turns) |
| tool_call_count | INTEGER | Number of tool calls made |
| input_tokens | INTEGER | Input token count (often 0 — see Known Limitations) |
| output_tokens | INTEGER | Output token count (often 0) |
| cache_read_tokens | INTEGER | Cache read tokens (often 0) |
| cache_write_tokens | INTEGER | Cache write tokens (often 0) |
| reasoning_tokens | INTEGER | Reasoning token count (often 0) |
| billing_provider | TEXT | Billing provider |
| billing_base_url | TEXT | API base URL |
| billing_mode | TEXT | Billing mode |
| estimated_cost_usd | REAL | Estimated cost in USD |
| actual_cost_usd | REAL | Actual cost in USD |

### `messages` table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (autoincrement) |
| session_id | TEXT | Foreign key to sessions.id |
| role | TEXT | `user`, `assistant`, `system`, `tool` |
| content | TEXT | Message content; for tools this may include results |
| tool_call_id | TEXT | Tool call ID |
| tool_calls | TEXT | JSON string of tool calls (preferred over tool_name) |
| tool_name | TEXT | Tool name (often NULL — see Known Limitations) |
| timestamp | REAL | Unix epoch timestamp (UTC) |
| token_count | INTEGER | Token count (often NULL) |
| finish_reason | TEXT | Finish reason (`stop`, `tool_calls`, etc.) |
| reasoning | TEXT | Reasoning content |
| reasoning_details | TEXT | Reasoning details |

### `session_topics` table

Maps topics to sessions. Join with sessions on `session_id`.

### Non-existent Columns (do not query)

The following columns are **NOT** present in `state.db`:
- `topic_hit`, `topic_skip` — TopicTracker counters are ephemeral and not persisted
- `compression_count` — Use `end_reason = 'compression'` instead
- `turn_count` — Use `message_count` (counts all messages, not turns)
- `duration_sec` — Calculate as `ended_at - started_at`
- `created_at` — Use `started_at` instead
- `name` — Use `source` instead

## Datetime Handling

All timestamps in `state.db` are Unix epoch seconds (floats, stored as UTC). Convert to Beijing time for display:

python
from datetime import datetime, timezone, timedelta
tz_bj = timezone(timedelta(hours=8))
cutoff = datetime.now(tz_bj) - timedelta(hours=4)
cutoff_ts = cutoff.timestamp()


## Diagnostic Queries

### Quick session summary (last 4 hours)

python
cur.execute("""
    SELECT COUNT(*),
           SUM(message_count), SUM(tool_call_count),
           AVG(message_count), MAX(message_count),
           SUM(input_tokens), SUM(output_tokens),
           SUM(CASE WHEN end_reason = 'max_iterations' THEN 1 ELSE 0 END),
           SUM(CASE WHEN end_reason = 'idle_timeout' THEN 1 ELSE 0 END),
           SUM(CASE WHEN end_reason = 'error' THEN 1 ELSE 0 END),
           SUM(CASE WHEN end_reason = 'compression' THEN 1 ELSE 0 END),
           COUNT(CASE WHEN ended_at IS NULL THEN 1 END) as active_sessions
    FROM sessions WHERE started_at > ?
""", (cutoff_ts,))


### Session health summary (last N hours)

python
cur.execute("""
    SELECT
        COUNT(*) as total_sessions,
        AVG(input_tokens) as avg_input,
        AVG(output_tokens) as avg_output,
        AVG(message_count) as avg_messages,
        SUM(input_tokens + output_tokens) as total_tokens,
        SUM(CASE WHEN ended_at IS NULL THEN 1 ELSE 0 END) as active_sessions,
        SUM(CASE WHEN end_reason = 'compression' THEN 1 ELSE 0 END) as compressions,
        SUM(CASE WHEN end_reason = 'error' THEN 1 ELSE 0 END) as errors,
        SUM(CASE WHEN end_reason = 'max_iterations' THEN 1 ELSE 0 END) as max_iterations
    FROM sessions WHERE started_at > ?
""", (cutoff_ts,))


### Session timeline (last N hours)

python
cur.execute("""
    SELECT id, started_at, ended_at, end_reason,
           message_count, tool_call_count, input_tokens, output_tokens, model
    FROM sessions
    WHERE ended_at > ? OR ended_at IS NULL
    ORDER BY ended_at DESC
    LIMIT 20
""", (cutoff_ts,))
for row in cur.fetchall():
    started = datetime.fromtimestamp(row[1], tz=tz_bj).strftime('%m-%d %H:%M')
    ended = datetime.fromtimestamp(row[2], tz=tz_bj).strftime('%m-%d %H:%M') if row[2] else 'ACTIVE'
    print(f"{row[0][:20]:<20} {started}~{ended} {row[3]:<15} "
          f"msg={row[4]:>3} tool={row[5]:>3} "
          f"in={row[6] if row[6] else 0:>6} out={row[7] if row[7] else 0:>6}")


### Sessions by end_reason (last N hours)

python
cur.execute("""
    SELECT end_reason, COUNT(*) as count
    FROM sessions
    WHERE started_at > ?
    GROUP BY end_reason
    ORDER BY count DESC
""", (cutoff_ts,))
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")


### Sessions by source (last N hours)

python
cur.execute("""
    SELECT source, COUNT(*) as sessions,
           SUM(message_count), SUM(tool_call_count),
           SUM(input_tokens), SUM(output_tokens),
           AVG(message_count)
    FROM sessions WHERE started_at > ?
    GROUP BY source ORDER BY sessions DESC
""", (cutoff_ts,))
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")


### Token usage summary

python
cur.execute("""
    SELECT 
        SUM(input_tokens) as total_in,
        SUM(output_tokens) as total_out,
        ROUND(AVG(NULLIF(input_tokens, 0)), 1) as avg_in_nonzero,
        ROUND(AVG(NULLIF(output_tokens, 0)), 1) as avg_out_nonzero,
        MAX(input_tokens) as max_in,
        MAX(output_tokens) as max_out
    FROM sessions
""")
row = cur.fetchone()
print(f"Total: {row[0]:,} in / {row[1]:,} out")
print(f"Avg (non-zero): {row[2]} in / {row[3]} out")
print(f"Max: {row[4]:,} in / {row[5]:,} out")


### Per-session breakdown with token efficiency

python
cur.execute("""
    SELECT
        id, model, message_count, tool_call_count,
        input_tokens, output_tokens, end_reason,
        ROUND((output_tokens * 1.0 / NULLIF(input_tokens, 0)), 2) as output_input_ratio
    FROM sessions WHERE started_at > ?
    ORDER BY message_count DESC LIMIT 20
""", (cutoff_ts,))


### High token sessions (context overflow risk)

python
cur.execute("""
    SELECT id, started_at, message_count, tool_call_count,
           input_tokens, output_tokens, end_reason
    FROM sessions
    WHERE input_tokens > 0
    ORDER BY input_tokens DESC
    LIMIT 10
""")
for row in cur.fetchall():
    started = datetime.fromtimestamp(row[1], tz=tz_bj).strftime('%m-%d %H:%M')
    print(f"  {row[0][:20]:<20} {started} msg={row[2]:>3} "
          f"in={row[4]:,} out={row[5]:,} {row[6]}")


### Active sessions (orphaned check)

python
cur.execute("""
    SELECT id, started_at, message_count, tool_call_count,
           ROUND((strftime('%s','now') - started_at) / 60.0, 1) as age_minutes
    FROM sessions
    WHERE ended_at IS NULL
    ORDER BY started_at ASC
""")
rows = cur.fetchall()
print(f"Active sessions: {len(rows)}")
for row in rows[:10]:
    started = datetime.fromtimestamp(row[1], tz=tz_bj).strftime('%m-%d %H:%M')
    print(f"  {row[0][:22]:<22} {started} msg={row[2]} tool={row[3]}")


### Tool call analysis from messages (via tool_calls JSON)

python
import json
cur.execute("""
    SELECT session_id, tool_calls, timestamp
    FROM messages
    WHERE tool_calls IS NOT NULL AND tool_calls != 'null'
    ORDER BY timestamp DESC LIMIT 100
""")
# Parse JSON: json.loads(row[1])[0]['function']['name']


### Error messages from messages table

python
# Note: errors are stored as assistant messages with 'error' or 'exception' in content.
# There is no `role = 'error'` in this schema.
cur.execute("""
    SELECT m.session_id, substr(m.content, 1, 200), m.timestamp
    FROM messages m
    JOIN sessions s ON m.session_id = s.id
    WHERE s.started_at > ? AND m.role = 'assistant'
    AND (m.content LIKE '%error%' OR m.content LIKE '%Exception%')
    ORDER BY m.timestamp DESC LIMIT 20
""", (cutoff_ts,))
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")


### Tool errors across sessions (last 24 hours)

python
cutoff_24h = (datetime.now(tz_bj) - timedelta(hours=24)).timestamp()
cur.execute("""
    SELECT session_id, tool_name, substr(content, 1, 100)
    FROM messages
    WHERE session_id IN (SELECT id FROM sessions WHERE started_at > ?)
      AND role = 'tool'
      AND (content LIKE '%error%'
           OR content LIKE '%Error%'
           OR content LIKE '%failed%'
           OR content LIKE '%not found%'
           OR content LIKE '%timeout%')
""", (cutoff_24h,))
errors = cur.fetchall()
print(f"Error events: {len(errors)}")
for s_id, tool, preview in errors[:10]:
    print(f"  [{s_id}] {tool}: {preview}")


**Known recurring error**: `"error": "127 — timeout: command not found"` on macOS indicates a missing system binary when using shell commands.

### Compression event analysis

python
cur.execute("""
    SELECT id, started_at, ended_at, message_count, tool_call_count,
           input_tokens, output_tokens, model
    FROM sessions
    WHERE end_reason = 'compression' AND started_at > ?
    ORDER BY started_at DESC
""", (cutoff_ts,))
for row in cur.fetchall():
    started = datetime.fromtimestamp(row[1], tz=tz_bj).strftime('%m-%d %H:%M')
    ended = datetime.fromtimestamp(row[2], tz=tz_bj).strftime('%m-%d %H:%M') if row[2] else 'ACTIVE'
    print(f"  {row[0][:20]:<20} {started}~{ended} "
          f"msg={row[3]} tool={row[4]}")


### TopicTracker context compaction detection

python
cur.execute("""
    SELECT session_id, substr(content, 1, 100)
    FROM messages
    WHERE content LIKE '%CONTEXT COMPACTION%'
    OR content LIKE '%topic tracker%'
    OR content LIKE '%topic_split%'
    ORDER BY timestamp DESC LIMIT 20
""")


### Token cost estimate

python
cur.execute("""
    SELECT SUM(input_tokens), SUM(output_tokens)
    FROM sessions WHERE ended_at > ?
""", (cutoff_ts,))
row = cur.fetchone()
in_tok = row[0] or 0
out_tok = row[1] or 0
# Approximate: $3.75/M input + $18.75/M output (Anthropic Sonnet 4)
cost = in_tok / 1e6 * 3.75 + out_tok / 1e6 * 18.75
print(f"Token estimate: {in_tok:,} in + {out_tok:,} out | ~${cost:.2f}")


## Skill Evolution Database

For skill performance and evolution metrics:

python
db_ev = sqlite3.connect(f"{os.path.expanduser('~')}/.hermes/evolution.db")
cur = db_ev.cursor()

# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
for row in cur.fetchall():
    print(row[0])


## Memory System Status

Check `~/.hermes/memories/` for memory file count and sizes:

bash
ls -la ~/.hermes/memories/


The `billing_provider` column in `sessions` table should be empty (built-in); if it shows a provider name, memory is backed by an external service.

## Health Log (SkillClaw Proxy)

bash
tail -50 ~/.skillclaw/health.log


Also check process health:

bash
ps aux | grep -E 'skillclaw-proxy|skillclaw-health' | grep -v grep


The proxy listens on port 30000.

## Health Indicators

| Metric | Healthy | Concern |
|--------|---------|----------|
| Compression rate | <5% of sessions end with `compression` | >10% suggests context window pressure |
| `input_tokens`/`output_tokens` | Non-zero values | All-zero indicates token tracking not working |
| Error rate | No sessions with `end_reason = 'error'` | Any errors need investigation |
| Active sessions | <50 sessions with `ended_at IS NULL` | >100 suggests orphaned/abandoned sessions |
| `max_iterations` rate | 0 | Any occurrences suggest runaway loops |
| `idle_timeout` rate | 0 | Non-zero suggests sessions hanging |
| `tool_name` coverage | Non-null for tool calls | All-null means tool_name tracking broken |
| `message_count` = total messages, not turns | Non-zero for ended sessions | 0 for active sessions is expected |
| Session file count vs DB | ~1:1 ratio | Large discrepancy suggests sync issues |

## Known Limitations

- **Token columns often zero**: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `reasoning_tokens` are frequently all-zero across all sessions even after sessions end. This is a billing/API limitation — the provider does not report token usage back to Hermes.
- **No per-message token breakdown**: Token counts stored in `messages.token_count` are also often NULL. Aggregate token stats from `sessions` table are the most reliable source.
- **No tool-specific statistics**: `messages.tool_name` is NULL for all tool calls. Tool usage must be inferred from `tool_calls` JSON column or from session JSON files.
- **TopicTracker is ephemeral**: TopicTracker hit/skip ratios, topic lists, and per-topic stats are NOT persisted anywhere — not in state.db, not in session JSONs. They exist only in live memory during an active session.
- **Timezone**: `started_at`, `ended_at`, and `timestamp` are Unix timestamps stored as UTC. Always convert with the user's configured timezone (e.g., `timezone(timedelta(hours=8))` for Beijing) when displaying human-readable times.
- **Session filenames encode Beijing time**: Session JSON files in `~/.hermes/sessions/` have filenames encoding Beijing time (e.g., `20260423_234411_eb7a01`). Python `mtime` returns UTC. When correlating files to DB records, convert timestamps accordingly.
- **Message content truncated**: `messages.content` may be compressed or truncated in the database. For full message content, read the session JSON files directly.
- **Active sessions have 0 message_count**: Sessions that have not ended (`ended_at` IS NULL) may have `message_count=0` in the DB even if messages exist. Use `COUNT(*)` from messages table for active sessions.
- **message_count = total messages, not turns**: A "turn" (user+assistant exchange) is typically 2 messages. Don't divide by 2.
- **system_messages table**: Exists in state.db but is empty in practice (0 rows). System prompts are embedded in message content, not stored separately.

## Common Rationalizations (Rats)

- "Token counts are zero so the session failed" → Actually, token counts are often zero in this environment even for successful sessions. Check `end_reason` and tool call counts instead.
- "No recent sessions found by mtime" → Session filenames encode Beijing time; Python mtime returns UTC. Use `state.db` for reliable session enumeration.
- "Compression events mean the session failed" → Context compaction is a normal handoff mechanism. Only count it as a problem if `end_reason` is `context_overflow` or errors follow.
- "sessions table is append-only" → Actually, completed sessions remain but active sessions may have null `ended_at`.

## Building a Context Health Report

A comprehensive health report should cover:

1. **Session summary**: Total sessions, active sessions, average messages, total tool calls
2. **End reason distribution**: How many completed normally vs. hit limits
3. **Compression analysis**: Sessions ending with `end_reason = 'compression'`
4. **Error summary**: Any sessions with `end_reason = 'error'`
5. **Orphaned sessions**: Active sessions with `ended_at IS NULL`, especially old ones
6. **Token usage**: Though often zero, report what's available
7. **Tool usage**: From `tool_calls` JSON column (not `tool_name`)
8. **Memory system status**: Check `~/.hermes/memories/` for memory files
9. **Config verification**: `~/.hermes/config.yaml` for model/provider settings
10. **SkillClaw health**: `~/.skillclaw/health.log` for routing health

## Session File Location

`~/.hermes/sessions/`

Each session has a JSON file named `{BeijingDateTime}_{randomId}.json`.
