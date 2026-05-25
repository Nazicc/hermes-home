#!/usr/bin/env python3
"""
hermes_to_evolver_bridge.py — Bridge Step 1

Syncs session data from Honcho's session store to the Evolver GEP directory,
and computes RTK (Runtime Knowledge) metrics for each session batch.

Outputs:
  - Session JSONL excerpts to hermes-agent-self-evolution/assets/gep/sessions/
  - RTK metrics to hermes-agent-self-evolution/assets/gep/rtk_metrics.jsonl

Idempotent: tracks last processed session in checkpoint file.
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ────────────────────────────────────────────────────────────────────
HERMES_DIR = Path.home() / ".hermes"
HONCHO_SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "hermes-agent" / "sessions"
EVOLVER_DIR = HERMES_DIR / "hermes-agent" / "hermes-agent-self-evolution"
GEP_DIR = EVOLVER_DIR / "assets" / "gep"
RTK_METRICS_FILE = GEP_DIR / "rtk_metrics.jsonl"
SESSIONS_OUT_DIR = GEP_DIR / "sessions"
CHECKPOINT = HERMES_DIR / ".bridge_last_session.txt"
BRIDGE_LOG = GEP_DIR / "bridge_step1.log"

MAX_SESSIONS_PER_RUN = 200  # Process up to 200 sessions per run


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(BRIDGE_LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_checkpoint() -> str:
    """Returns the last processed session ID, or empty string."""
    if CHECKPOINT.exists():
        return CHECKPOINT.read_text().strip()
    return ""


def save_checkpoint(session_id: str):
    CHECKPOINT.write_text(session_id)


def get_session_files():
    """Returns sorted session JSONL files newer than checkpoint."""
    checkpoint = load_checkpoint()
    all_files = sorted(HONCHO_SESSIONS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    
    if not checkpoint:
        return all_files[:MAX_SESSIONS_PER_RUN]
    
    # Find files after checkpoint
    result = []
    found = False
    for f in all_files:
        if found:
            result.append(f)
            if len(result) >= MAX_SESSIONS_PER_RUN:
                break
        elif f.name == checkpoint:
            found = True
    return result


def parse_session_file(path: Path) -> dict:
    """Parse a session JSONL file and extract metrics."""
    messages = []
    tool_calls = 0
    error_count = 0
    user_msgs = 0
    assistant_msgs = 0
    tool_uses = 0
    tokens_estimate = 0
    
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    messages.append(msg)
                    
                    msg_type = msg.get("type", "")
                    if msg_type == "user":
                        user_msgs += 1
                    elif msg_type == "assistant":
                        assistant_msgs += 1
                    elif msg_type == "tool_use":
                        tool_uses += 1
                        tool_calls += 1
                        content = msg.get("content", "")
                        if "error" in content.lower() or "exception" in content.lower():
                            error_count += 1
                    
                    # Estimate tokens from content
                    content = str(msg.get("content", ""))
                    tokens_estimate += len(content) // 4
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        log(f"WARNING: failed to parse {path.name}: {e}")
        return None
    
    if not messages:
        return None
    
    # Get session metadata from first system message
    session_id = path.stem  # filename without extension
    source = "unknown"
    model = "unknown"
    started_at = ""
    
    for msg in messages:
        if msg.get("type") == "system":
            content = msg.get("content", "")
            if "source=" in content:
                for part in content.split():
                    if part.startswith("source="):
                        source = part.split("=", 1)[1].strip()
                    elif part.startswith("model="):
                        model = part.split("=", 1)[1].strip()
                    elif part.startswith("timestamp="):
                        started_at = part.split("=", 1)[1].strip()
            break
    
    return {
        "session_id": session_id,
        "source": source,
        "model": model,
        "started_at": started_at,
        "total_messages": len(messages),
        "user_messages": user_msgs,
        "assistant_messages": assistant_msgs,
        "tool_uses": tool_uses,
        "error_count": error_count,
        "error_rate": error_count / max(tool_uses, 1),
        "tokens_estimate": tokens_estimate,
        "path": str(path),
    }


def compute_rtk_metrics(sessions: list[dict]) -> dict:
    """Compute aggregate RTK metrics from session data."""
    if not sessions:
        return {
            "signal_score": 0.0,
            "quality_score": 0.0,
            "tokens_used": 0,
            "sessions_analyzed": 0,
            "active_sessions": 0,
            "error_rate": 0.0,
            "tool_calls": 0,
        }
    
    total_errors = sum(s.get("error_count", 0) for s in sessions)
    total_tool_calls = sum(s.get("tool_uses", 0) for s in sessions)
    total_tokens = sum(s.get("tokens_estimate", 0) for s in sessions)
    active_sessions = sum(1 for s in sessions if s.get("total_messages", 0) >= 3)
    
    # Quality score: penalize errors, reward engagement
    quality = 1.0 - (total_errors / max(total_tool_calls, 1)) * 0.5
    quality = max(0.0, min(1.0, quality))
    
    # Signal score based on error rate and engagement
    error_rate = total_errors / max(total_tool_calls, 1)
    signal_score = 1.0 - (error_rate * 0.5 + (1 - active_sessions / max(len(sessions), 1)) * 0.3)
    signal_score = max(0.0, min(1.0, signal_score))
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": "cron_analysis",
        "signal_score": round(signal_score, 3),
        "quality_score": round(quality, 3),
        "tokens_used": total_tokens,
        "sessions_analyzed": len(sessions),
        "active_sessions": active_sessions,
        "error_rate": round(error_rate, 4),
        "tool_calls": total_tool_calls,
    }


def append_rtk_metrics(metrics: dict):
    """Append RTK metrics to the output file."""
    GEP_DIR.mkdir(parents=True, exist_ok=True)
    with open(RTK_METRICS_FILE, "a") as f:
        f.write(json.dumps(metrics) + "\n")


def copy_session_excerpt(path: Path, session_data: dict):
    """Copy a session excerpt to the output directory."""
    SESSIONS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SESSIONS_OUT_DIR / path.name
    # Just link/copy the file
    import shutil
    try:
        shutil.copy2(path, out_path)
    except Exception as e:
        log(f"WARNING: failed to copy session {path.name}: {e}")


def main():
    print("=" * 60)
    log("hermes_to_evolver_bridge.py — START (Step 1 of 3)")
    
    # Get session files to process
    session_files = get_session_files()
    log(f"Found {len(session_files)} sessions to process")
    
    if not session_files:
        log("No new sessions to process. Done.")
        return 0
    
    processed = 0
    sessions_data = []
    
    for path in session_files:
        data = parse_session_file(path)
        if data:
            sessions_data.append(data)
            copy_session_excerpt(path, data)
            processed += 1
            save_checkpoint(path.name)
    
    log(f"Processed {processed} sessions")
    
    # Compute and save RTK metrics
    if sessions_data:
        metrics = compute_rtk_metrics(sessions_data)
        append_rtk_metrics(metrics)
        log(f"RTK metrics: signal_score={metrics['signal_score']}, quality_score={metrics['quality_score']}, sessions={metrics['sessions_analyzed']}, tool_calls={metrics['tool_calls']}")
    
    log(f"hermes_to_evolver_bridge.py — DONE (Step 1 of 3)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
