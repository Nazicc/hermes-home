#!/usr/bin/env python3
"""
SimpleMem Memory Hook Handler

Reference implementation for the simplemem_memory hook.
Can also be run standalone: python3 handler.py --session-id SESSION_ID

When Gateway hook system is implemented, this is called on session_compact events.
For now, simplemem-memory-bridge cron job (every 30min) provides the live triggering.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

BRIDGE_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "simplemem_memory_bridge.py"


def handle_session(session_id: str, source: str = "feishu") -> dict:
    """
    Handle a single session end event.
    Called by the hook system when session_compact fires.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path.home() / ".hermes"))

    from simplemem_evolution.working_memory import WorkingMemoryStore, WorkingMemoryEntry
    from simplemem_evolution.forgetting import EvolutionStore
    import sqlite3
    from datetime import datetime, timezone

    HERMES_DB = Path.home() / ".hermes" / "state.db"
    results = {"working_memory": 0, "evolution": 0, "errors": []}

    try:
        conn = sqlite3.connect(str(HERMES_DB))
        conn.row_factory = sqlite3.Row

        # Read session metadata
        cur = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND source = ?",
            (session_id, source)
        )
        session = cur.fetchone()
        if not session:
            return {"error": f"Session {session_id} not found"}

        # Read messages
        cur = conn.execute(
            "SELECT role, content, tool_calls FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        )
        messages = [dict(r) for r in cur.fetchall()]
        conn.close()

        # Extract entries (simplified — full logic in bridge script)
        entries = _extract_entries(session, messages)

        # Write to Working Memory + Evolution
        wm = WorkingMemoryStore()
        evo = EvolutionStore()

        for entry in entries[:7]:
            try:
                wmentry = WorkingMemoryEntry(
                    entry_id=entry["id"],
                    summary=entry.get("title", "")[:100],
                    importance_score=entry.get("importance", 0.5),
                )
                if wm.add(wmentry):
                    results["working_memory"] += 1
            except Exception as e:
                results["errors"].append(f"WM: {e}")

            try:
                evo.upsert(
                    entry_id=entry["id"],
                    content=entry["content"][:1000],
                    weight=entry.get("importance", 0.5),
                )
                results["evolution"] += 1
            except Exception as e:
                results["errors"].append(f"Evo: {e}")

        return results

    except Exception as e:
        return {"error": str(e)}


def _extract_entries(session, messages) -> list:
    """Simplified entry extraction from session + messages."""
    from datetime import datetime, timezone  # local import to avoid top-level dependency
    sid = session["id"]
    started = datetime.fromtimestamp(session["started_at"], tz=timezone.utc).strftime('%Y-%m-%d %H:%M')

    entries = [{
        "id": f"session-{sid[:16]}",
        "category": "checkpoint",
        "title": f"会话 {started}",
        "content": f"Feishu会话 {sid[:20]} | {session['message_count']} msgs | {session['tool_call_count']} tools",
        "importance": 0.6,
    }]

    # Extract significant tool calls
    for m in messages:
        tc = m.get("tool_calls")
        if tc and m["role"] == "assistant":
            try:
                for call in json.loads(tc) or []:
                    fn = call.get("function", {})
                    name = fn.get("name", "")
                    if name in {"terminal", "patch", "write_file", "delegate_task", "cronjob"}:
                        entries.append({
                            "id": f"{sid[:16]}-tool-{name}",
                            "category": "pattern",
                            "title": f"工具: {name}",
                            "content": f"{name}({json.dumps(fn.get('arguments',''))[:200]})",
                            "importance": 0.7,
                        })
            except (json.JSONDecodeError, TypeError):
                pass

    return entries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SimpleMem Memory Hook Handler")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--source", default="feishu")
    args = parser.parse_args()

    result = handle_session(args.session_id, args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if "error" not in result else 1)
