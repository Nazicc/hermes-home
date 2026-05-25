#!/usr/bin/env python3
"""
SimpleMem Memory Bridge — Session → SimpleMem Evolution MCP

Reads newly-completed feishu sessions from SQLite (end_reason='compression'),
extracts significant content, and writes to:
  1. SimpleMem Evolution — working memory (7-slot cache)
  2. Hindsight VectorDB — via REST API

Cron: runs every 30min (same schedule as evolver-bridge).
The evolver-bridge (240min) handles SQLite → evolver sessions dir separately.
This bridge handles Session → SimpleMem Evolution → Hindsight pipeline.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Config ──────────────────────────────────────────────────────────────────
HERMES_DB = Path.home() / ".hermes" / "state.db"
STATE_FILE = Path.home() / ".hermes" / ".bridge_last_session.txt"
EVOLUTION_DB = Path.home() / ".hermes" / "simplemem_evolution" / "evolution.db"

# State file stores: last_processed_ended_at timestamp (for ordering by end time)
# This is more stable than session ID ordering (some sessions close out of started_at order)

# Batch limit — process at most this many sessions per invocation
# to avoid being killed by agent timeout (exit 143 = SIGTERM).
# Remaining sessions are picked up on the next 30-min cron cycle.
MAX_SESSIONS_PER_RUN = 5

# What constitutes "significant" content to save
MIN_SESSION_MSGS = 3
MAX_CONTENT_LEN = 3000
SIGNIFICANT_TOOLS = {
    "memory", "mcp_simplemem", "mcp_beads", "terminal", "patch",
    "write_file", "delegate_task", "cronjob", "mcp_tool",
    "image_generate", "feishu_doc", "send_message"
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_last_ended_at() -> Optional[float]:
    """Read last processed ended_at timestamp from state file."""
    if not STATE_FILE.exists():
        return None
    content = STATE_FILE.read_text().strip()
    if not content:
        return None
    # File format: "ended_at\nsid" (written by set_last_ended_at)
    first_line = content.split('\n')[0].strip()
    try:
        return float(first_line)
    except ValueError:
        return None

def set_last_ended_at(ended_at: float, sid: str):
    """Save the ended_at timestamp and session ID to state file."""
    STATE_FILE.write_text(f"{ended_at}\n{sid}")

def truncate(text: str, max_len: int = MAX_CONTENT_LEN) -> str:
    if not text:
        return ""
    return text[:max_len] + ("..." if len(text) > max_len else "")

def extract_new_sessions(db_path: Path, since_ended_at: Optional[float] = None):
    """Read feishu sessions that ended normally since last run, ordered by ended_at."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    if since_ended_at is not None:
        cur = conn.execute("""
            SELECT id, source, model, started_at, ended_at, end_reason,
                   message_count, tool_call_count, title
            FROM sessions
            WHERE source = 'feishu'
              AND end_reason IN ('compression', 'error', 'max_turns')
              AND message_count >= ?
              AND ended_at > ?
            ORDER BY ended_at ASC
        """, (MIN_SESSION_MSGS, since_ended_at))
    else:
        cur = conn.execute("""
            SELECT id, source, model, started_at, ended_at, end_reason,
                   message_count, tool_call_count, title
            FROM sessions
            WHERE source = 'feishu'
              AND end_reason IN ('compression', 'error', 'max_turns')
              AND message_count >= ?
            ORDER BY ended_at ASC
        """, (MIN_SESSION_MSGS,))

    sessions = [dict(row) for row in cur.fetchall()]
    conn.close()
    return sessions

def read_messages(db_path: Path, session_id: str):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.execute("""
        SELECT role, content, tool_calls, tool_name, timestamp
        FROM messages
        WHERE session_id = ?
        ORDER BY timestamp ASC
    """, (session_id,))
    msgs = [dict(r) for r in cur.fetchall()]
    conn.close()
    return msgs

def extract_entries(session: dict, messages: list) -> list:
    """Extract significant memory-worthy content blocks from a session."""
    entries = []
    sid = session["id"]
    started = datetime.fromtimestamp(session["started_at"], tz=timezone.utc)
    started_str = started.strftime('%Y-%m-%d %H:%M')

    # Parse tool calls
    tool_calls = []
    for m in messages:
        tc_str = m.get("tool_calls")
        if tc_str and m["role"] == "assistant":
            try:
                tool_calls.extend(json.loads(tc_str) or [])
            except (json.JSONDecodeError, TypeError):
                pass

    tool_names_used = set()
    for tc in tool_calls:
        fn = tc.get("function", {})
        name = fn.get("name", "")
        if name:
            tool_names_used.add(name)

    # ── Session summary ───────────────────────────────────────────────────────
    summary_lines = [
        f"Feishu会话 {sid[:20]}",
        f"时间: {started_str}",
        f"消息数: {session['message_count']} | 工具调用: {session['tool_call_count']}",
    ]
    if tool_names_used:
        summary_lines.append(f"使用的工具: {', '.join(sorted(tool_names_used))}")
    if session.get("title"):
        summary_lines.append(f"主题: {session['title']}")

    entries.append({
        "id": f"session-{sid[:16]}",
        "category": "checkpoint",
        "title": f"会话 {started_str}",
        "content": "\n".join(summary_lines),
        "importance": 0.6,
    })

    # ── User messages (first + last significant) ───────────────────────────────
    user_msgs = [m for m in messages if m["role"] == "user"]
    for idx, label in [(0, "start"), (-1, "end")]:
        if idx < len(user_msgs):
            content = truncate(user_msgs[idx].get("content", ""))
            if len(content) > 30:
                entries.append({
                    "id": f"{sid[:16]}-user-{label}",
                    "category": "lesson",
                    "title": f"用户{'首' if label=='start' else '末'}条消息: {content[:60]}",
                    "content": content,
                    "importance": 0.5,
                })

    # ── Significant tool actions ───────────────────────────────────────────────
    for tc in tool_calls:
        fn = tc.get("function", {})
        name = fn.get("name", "")
        if name in SIGNIFICANT_TOOLS:
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except:
                    args = {"raw": args[:200]}
            args_str = json.dumps(args, ensure_ascii=False)[:400] if isinstance(args, dict) else str(args)[:400]
            entries.append({
                "id": f"{sid[:16]}-tool-{name}",
                "category": "pattern",
                "title": f"工具调用: {name}",
                "content": f"工具: {name}\n参数: {args_str}",
                "importance": 0.7,
            })

    # ── Structured assistant responses (reports, analysis) ─────────────────────
    for m in messages:
        if m["role"] == "assistant":
            content = (m.get("content") or "")[:4000]
            if len(content) > 300 and ("##" in content or "```" in content or len(content) > 1000):
                entries.append({
                    "id": f"{sid[:16]}-response",
                    "category": "lesson",
                    "title": f"Agent回复: {content[:80].strip()}",
                    "content": truncate(content, 2000),
                    "importance": 0.4,
                })

    return entries

# ── SimpleMem Evolution store ──────────────────────────────────────────────────

def add_to_evolution(entries: list) -> dict:
    """Add entries to SimpleMem Evolution working memory + long-term store."""
    stats = {"working_memory": 0, "evolution": 0, "errors": 0}

    # Import the simplemem_evolution package
    # Package lives at ~/.hermes/simplemem_evolution/, parent ~/.hermes/ must be in path
    pkg_parent = Path.home() / ".hermes"
    if str(pkg_parent) not in sys.path:
        sys.path.insert(0, str(pkg_parent))

    try:
        from simplemem_evolution.working_memory import WorkingMemoryStore, WorkingMemoryEntry
        from simplemem_evolution.forgetting import EvolutionStore

        wm = WorkingMemoryStore()
        evo = EvolutionStore()

        # Sort by importance descending, take top entries
        sorted_entries = sorted(entries, key=lambda e: e.get("importance", 0.5), reverse=True)

        for entry in sorted_entries[:7]:  # 7-slot working memory limit
            eid = entry["id"]
            content = entry["content"]
            importance = entry.get("importance", 0.5)

            # Add to working memory (takes WorkingMemoryEntry model)
            try:
                wmentry = WorkingMemoryEntry(
                    entry_id=eid,
                    summary=entry.get("title", "")[:100],
                    importance_score=importance,
                )
                if wm.add(wmentry):
                    stats["working_memory"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"[bridge] working_memory add error: {e}")

            # Add to evolution store (takes upsert with individual params)
            try:
                evo.upsert(
                    entry_id=eid,
                    content=content[:1000],
                    weight=importance,
                )
                stats["evolution"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"[bridge] evolution upsert error: {e}")

    except ImportError as e:
        print(f"[bridge] Import error: {e}")
        stats["errors"] += 1

    return stats

# ── Hindsight VectorDB ────────────────────────────────────────────────────────

def add_to_hindsight(entries: list, session_id: str) -> int:
    """Write entries to Hindsight VectorDB via REST API (batch format)."""
    hindsight_url = os.environ.get("HINDSIGHT_API_URL", "http://127.0.0.1:18888")
    bank_id = "hermes-agent"
    count = 0

    # Filter to most important entries only
    important = [e for e in entries if e.get("importance", 0) >= 0.6]
    if not important:
        important = entries[:2]

    # Batch: Hindsight API expects {"items": [{"content": "...", "tags": [...]}]}
    items = [
        {
            "content": entry["content"][:2000],
            "tags": [entry.get("category", "lesson")],
        }
        for entry in important[:10]
    ]

    if not items:
        return 0

    try:
        req = urllib.request.Request(
            f"{hindsight_url}/v1/default/banks/{bank_id}/memories",
            data=json.dumps({"items": items}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            if result.get("success"):
                count = result.get("items_count", len(items))
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:100]
        print(f"[bridge] Hindsight HTTP {e.code}: {body}")
    except Exception as e:
        if "Connection refused" not in str(e) and "timed out" not in str(e).lower():
            print(f"[bridge] Hindsight: {e}")
    return count

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ts = datetime.now().isoformat()
    print(f"[bridge] SimpleMem Memory Bridge — {ts}")

    if not HERMES_DB.exists():
        print(f"[bridge] ERROR: {HERMES_DB} not found")
        return

    last_ended_at = get_last_ended_at()
    sessions = extract_new_sessions(HERMES_DB, last_ended_at)
    last_sid_str = STATE_FILE.read_text().strip().split('\n')[-1] if STATE_FILE.exists() else None
    print(f"[bridge] {len(sessions)} new sessions to process (last ended: {last_sid_str or 'none'})")

    total_wm = 0
    total_evo = 0
    total_hindsight = 0
    processed = 0

    for session in sessions:
        if processed >= MAX_SESSIONS_PER_RUN:
            remaining = len(sessions) - processed
            print(f"[bridge] Batch limit ({MAX_SESSIONS_PER_RUN}) reached, {remaining} sessions deferred to next cycle.")
            break
        processed += 1
        sid = session["id"]
        msgs = read_messages(HERMES_DB, sid)
        entries = extract_entries(session, msgs)
        print(f"[bridge] {sid[:20]}: {len(entries)} entries, {session['message_count']} msgs")

        evo_stats = add_to_evolution(entries)
        n_h = add_to_hindsight(entries, sid)

        total_wm += evo_stats["working_memory"]
        total_evo += evo_stats["evolution"]
        total_hindsight += n_h

        print(f"[bridge]   → WM: +{evo_stats['working_memory']} | Evolution: +{evo_stats['evolution']} | Hindsight: +{n_h}")
        set_last_ended_at(session["ended_at"], sid)

    print(f"[bridge] Done. WM:+{total_wm} Evo:+{total_evo} Hindsight:+{total_hindsight} across {len(sessions)} sessions.")

if __name__ == "__main__":
    main()
