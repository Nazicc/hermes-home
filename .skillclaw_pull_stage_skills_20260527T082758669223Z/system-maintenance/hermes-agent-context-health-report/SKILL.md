---
name: hermes-agent-context-health-report
description: 生成 hermes-agent 上下文健康报告 — 会话统计（state.db）、记忆状态（memories/）、Token 使用、错误摘要。数据源为 session JSON 文件 + state.db (SQLite) + memories/ 目录。
category: system-maintenance
---

---
name: hermes-agent-context-health-report
description: 生成 hermes-agent 上下文健康报告 — 会话统计（state.db）、记忆状态（memories/）、Token 使用、错误摘要。数据源为 session JSON 文件 + state.db (SQLite) + memories/ 目录。
trigger: hermes context health report
trigger_categories: [system-maintenance, diagnostics]
created: 2026-05-02
updated: 2026-05-02
---

# Hermes Context Health Report

生成 hermes-agent 系统的上下文健康报告，涵盖会话统计、记忆容量、Token 使用、Topic-Tracker、以及错误摘要。

## 数据源一览

| 数据 | 源 | 路径 |
|------|----|----|
| 会话统计/错误 | state.db (SQLite) | `~/.hermes/state.db` |
| 记忆文件 | memories/ | `~/.hermes/memories/MEMORY.md`, `USER.md` |
| Topic-Tracker | state.db | `topic_tracker` 表（可能不存在） |
| Session JSON | sessions/ | `~/.hermes/sessions/session_*.json` |
| 配置 | config.yaml | `~/.hermes/config.yaml` |

## 1. 会话统计 (state.db)

**Python 代码**（注意 timezone 导入方式）：

python
import sqlite3, os
from datetime import datetime, timezone, timedelta

tz_beijing = timezone(timedelta(hours=8))
now_utc8 = datetime.now(tz_beijing)
lookback_hours = 4
four_hours_ago_ts = (now_utc8 - timedelta(hours=lookback_hours)).timestamp()

state_db = os.path.expanduser("~/.hermes/state.db")
conn = sqlite3.connect(state_db)
cur = conn.cursor()

# 基本统计
cur.execute("""
  SELECT COUNT(*), SUM(message_count), SUM(tool_calls_made),
         SUM(input_tokens), SUM(output_tokens), SUM(reasoning_tokens)
  FROM sessions WHERE started_at >= ?
""", (four_hours_ago_ts,))
row = cur.fetchone()
print(f"Sessions: {row[0]}, Msgs: {row[1]}, Tools: {row[2]}, "
      f"InToks: {row[3]}, OutToks: {row[4]}, ReaToks: {row[5]}")

# 压缩事件（context compaction）
cur.execute("""
  SELECT session_id, ended_reason FROM sessions 
  WHERE started_at >= ? AND ended_reason = 'compression'
""", (four_hours_ago_ts,))
compressions = cur.fetchall()
print(f"Compressions: {len(compressions)}")

# 工具错误（exit_code != 0）
cur.execute("""
  SELECT session_id, exit_code, tool_name, error_msg
  FROM tool_errors WHERE session_id IN 
  (SELECT session_id FROM sessions WHERE started_at >= ?)
  ORDER BY tool_errors.created_at DESC
  LIMIT 20
""", (four_hours_ago_ts,))
errors = cur.fetchall()
for e in errors:
    print(f"  [{e[0][:16]}] exit={e[1]} tool={e[2]} err={e[3]}")


**SQL 直接查询**（可选）：

sql
SELECT COUNT(*) FROM sessions WHERE started_at >= ?;
SELECT session_id, ended_reason, message_count FROM sessions 
  WHERE started_at >= ? ORDER BY message_count DESC LIMIT 5;
SELECT * FROM tool_errors ORDER BY created_at DESC LIMIT 20;


**注意事项**：
- `input_tokens`, `output_tokens`, `reasoning_tokens` 在某些 provider（如 MiniMax-M2.7）下可能为 0，这是 provider 层面的统计缺失，不影响会话本身
- 正常结束的 cron session 的 `ended_reason` 为 `cron_complete`，不是 `compression`
- `topic_tracker` 表可能不存在于 schema v6 中

## 2. Topic-Tracker

**警告**：`topic_tracker` 表在当前 state.db (schema v6) 中不存在。不要浪费时间查询或分析 Topic-Tracker 数据。如果需要 Topic-Tracker 功能，需要先确认其实现状态。

如果表中存在，查询方式：

python
cur.execute("SELECT * FROM topic_tracker ORDER BY updated_at DESC LIMIT 20")
rows = cur.fetchall()
print(f"TopicTracker entries: {len(rows)}")


## 3. 记忆状态 (memories/)

python
import os

mem_dir = os.path.expanduser("~/.hermes/memories/")
for fname in ['MEMORY.md', 'USER.md']:
    fpath = os.path.join(mem_dir, fname)
    if os.path.exists(fpath):
        with open(fpath) as fp:
            content = fp.read()
        print(f"{fname}: {len(content)} chars")


**关注点**：
- `MEMORY.md` 有容量阈值（如 2,200 chars），超过会触发压缩警告
- 如果接近阈值，报告 `MEMORY.md` 容量状态

## 4. Session JSON 文件（详细错误分析）

对于高错误率或长会话，深入读取 session JSON 文件：

python
import json, glob, os
from datetime import datetime, timezone, timedelta

tz_beijing = timezone(timedelta(hours=8))
now_utc8 = datetime.now(tz_beijing)
four_hours_ago = now_utc8 - timedelta(hours=4)

session_files = glob.glob(os.path.expanduser("~/.hermes/sessions/session_*.json"))
recent = []
for f in session_files:
    mtime = datetime.fromtimestamp(os.path.getmtime(f), tz=tz_beijing)
    if mtime >= four_hours_ago:
        recent.append(f)

recent.sort(key=os.path.getmtime)
print(f"Recent sessions: {len(recent)}")

# 读取最新的 session 找错误
if recent:
    with open(recent[-1]) as fp:
        sess = json.load(fp)
    
    # 找工具调用和错误
    for msg in sess.get('messages', []):
        if msg.get('type') == 'tool_call':
            if msg.get('error') or msg.get('exit_code', 0) != 0:
                print(f"Tool error: {msg.get('name')} - {msg.get('error')}")


**关注点**：
- `exit_code=124` 通常是超时
- `exit_code=1` 需要结合 `error` 字段判断
- 内存限制警告（memory limit exceeded）表示上下文快满

## 5. 错误摘要

报告格式：


## Context Health Report

**Time range**: last 4 hours (Beijing time)

### Sessions
- Total sessions: N
- Total messages: N
- Avg messages/session: N
- Compressions: N

### Token Usage
- Note: Token stats may be 0 for MiniMax-M2.7 provider

### Memory
- MEMORY.md: N chars
- USER.md: N chars

### Topic-Tracker
- WARNING: Not available in current state.db schema v6

### Tool Errors (last 4h)
- Total: N
- [session_id] exit=N tool=N err=N

### Recommendations
- [action items based on findings]


## 已知环境限制

1. **Token 统计缺失**：MiniMax-M2.7 provider 不记录 input/output/reasoning tokens 到 state.db
2. **Topic-Tracker 不可用**：`topic_tracker` 表不存在于 schema v6
3. **Skill 保存限制**：使用 `skill_manage` create 保存本 skill 时，agent-created 源代码会触发安全扫描，若内容包含 `~/.hermes/config.yaml` 路径引用会标记 CRITICAL persistence
