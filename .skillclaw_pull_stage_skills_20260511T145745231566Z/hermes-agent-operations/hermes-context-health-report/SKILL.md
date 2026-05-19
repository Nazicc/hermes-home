---
name: hermes-context-health-report
description: "Generate a context health report for Hermes Agent — session stats, memory state, token usage, TopicTracker status, and error summary from session logs. Covers known data gaps and caveats. NOT for real-time monitoring (use skillclaw-health.sh instead) or for detailed per-message token analysis (requires SQLite state.db query)."
category: hermes-agent-operations
---

---
name: hermes-context-health-report
description: Generate context health report for Hermes Agent by analyzing session logs, memory state, and config
triggers:
  - "上下文健康报告"
  - "健康报告"
  - "context health report"
  - "session report"
  - "hermes-agent health"
tags: [hermes, diagnostics, monitoring]
category: hermes-agent-operations
---

# hermes-context-health-report

Generate a context health report for Hermes Agent by analyzing session logs, memory state, and config. Produces a structured Markdown report with session summary, memory system status, token usage, TopicTracker status, error summary, and improvement suggestions.

## Data Sources

| Source | Path | What it provides |
|--------|------|------------------|
| Session logs | `~/.hermes/sessions/session_*.json` | Message counts, iteration counts, token estimates, errors per session |
| Memory files | `~/.hermes/memories/MEMORY.md`, `~/.hermes/memories/USER.md` | Memory system state and size |
| Config | `~/.hermes/config.yaml` | Memory provider, model routing |
| State DB | `~/.hermes/state.db` (SQLite) | Exact token counts, compression triggers, TopicTracker stats (optional, requires sqlite3) |

## Session File Naming

Session files follow the pattern: `session_<role>_<hash>_<date>_<time>.json`

**Examples:**
- `session_user_a1b2c3d4_20260507_001230.json`
- `session_cron_9f8e7d6c_20260507_060000.json`
- `session_00_00aabbcc_20260507_003045.json`

Role values: `user`, `cron`, or numeric (`00`, `01`, etc.). Extract timestamps from the filename (`<date>_<time>`), not from JSON `created_at` fields, which may not be present.

## Report Sections

### 1. Session Summary

Parse all `~/.hermes/sessions/session_*.json` files from the last 4 hours (filter by filename timestamp). Compute:
- **Session count** (total sessions in window)
- **Total messages** (sum of all messages across sessions)
- **Avg messages per session** (total messages / session count)
- **Max iterations** (max `user_messages_count` in any single session — indicates longest conversation)
- **Largest session** (session with most messages, note session name)

**Observations:** Note whether sessions are predominantly single-turn (cron calls) or multi-turn (interactive sessions). Identify outlier sessions with high message counts.

### 2. Memory System Status

Check the memory provider from `config.yaml`. Read `~/.hermes/memories/MEMORY.md` and `~/.hermes/memories/USER.md` to assess:
- **Total character count** across both files
- **Last update timestamps** (grep for YYYY-MM-DD patterns)
- **Key topic coverage** (brief summary of what's stored)
- **Memory provider** (from config: e.g., `openviking`, `simplemem`, `sqlite`)

### 3. Token Usage Analysis

**IMPORTANT: Known Data Gaps**

- Session JSON files do **NOT** contain direct token counts. JSON fields for tokens are typically absent or 0.
- To get exact token counts, query the SQLite state.db: `sqlite3 ~/.hermes/state.db "SELECT prompt_tokens, completion_tokens, total_tokens FROM conversation_stats ORDER BY id DESC LIMIT 10"`
- As a fallback, estimate token usage by summing character counts across session messages and dividing by 4 (rough approximation: 1 token ≈ 4 characters)

**Compression status:** Check for `"context_compressed": true` or compression trigger events in session JSON. If sessions exceed 30k tokens but compression triggers = 0, flag this as a potential issue.

### 4. TopicTracker Status

**IMPORTANT: Known Data Gap**

- TopicTracker hit/skip statistics are NOT stored in session JSON files.
- The `TopicTracker` object is internal to the agent runtime and not serialized to session logs.
- To check TopicTracker status, either:
  1. Query `~/.hermes/state.db`: `sqlite3 ~/.hermes/state.db "SELECT name, hit_count, skip_count FROM topic_tracker ORDER BY hit_count DESC LIMIT 10"`
  2. Or check agent runtime logs for `TopicTracker` debug output

Report "Not available in session JSON" and note that state.db query is needed for accurate stats.

### 5. Error Summary

Parse session JSON files for `"error"` or `"error_type"` fields. Group errors by type:
- **FileNotFoundError** — Missing files referenced in the conversation
- **KeyError / IndexError** — Missing keys in JSON responses or list index out of range
- **HTTP errors** — API failures (check for `status_code` fields)
- **Tool call failures** — MCP tool execution errors

Report **error rate** (sessions with errors / total sessions) and list the top error types with session names where they occurred.

### 6. Suggestions

Based on findings, provide actionable recommendations:
- If error rate > 30%: Investigate the dominant error type and check relevant skill documentation
- If memory size > 10,000 chars: Suggest memory consolidation or pruning
- If no compression triggers despite high token counts: Flag for investigation
- If TopicTracker has low hit rates: Suggest reviewing topic definitions
- If sessions are mostly single-turn: Note this is normal for cron-based deployments

## Output Format

markdown
# 上下文健康报告
**生成时间**: <YYYY-MM-DD HH:MM:SS TZ>
**统计周期**: 最近 <N> 小时

---

## 1. 会话摘要
[table with metrics]
[observations]

## 2. 内存系统状态
[memory provider, file sizes, last update, key topics]

## 3. Token 使用分析
[estimates or SQLite query results]
[compression status]

## 4. TopicTracker 状态
[not available in JSON / SQLite query results]

## 5. 错误摘要
[error rate, top error types with session names]

## 6. 改进建议
[actionable recommendations based on findings]


## Known Limitations

1. **No direct token counts in JSON** — Must use SQLite state.db for accurate token data
2. **No TopicTracker stats in JSON** — Must use SQLite or runtime logs
3. **Session filename timestamps** — Use filename date/time, not JSON `created_at`
4. **Time window filtering** — Filter by filename date (YYYYMMDD) and time (HHMMSS) manually, no built-in time filter
5. **Error field names vary** — Check for `error`, `error_type`, `exception`, or tool-specific error schemas

