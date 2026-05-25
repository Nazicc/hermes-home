#!/usr/bin/env python3
"""
evolver_analysis.py — Bridge Step 2

Analyzes RTK metrics and session data to generate evolution signals.
Outputs updated signals.json and events.jsonl for the Evolver pipeline.

Signal types detected:
  - errsig: High error rate in tool usage
  - context_bloat: Excessive message count suggesting context issues
  - low_engagement: Low active session ratio
  - skill_drift: Changes in tool usage patterns
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ────────────────────────────────────────────────────────────────────
HERMES_DIR = Path.home() / ".hermes"
EVOLVER_DIR = HERMES_DIR / "hermes-agent" / "hermes-agent-self-evolution"
GEP_DIR = EVOLVER_DIR / "assets" / "gep"
RTK_METRICS_FILE = GEP_DIR / "rtk_metrics.jsonl"
SIGNALS_FILE = GEP_DIR / "signals.json"
EVENTS_FILE = GEP_DIR / "events.jsonl"
CHECKPOINT = GEP_DIR / ".analysis_checkpoint.txt"
BRIDGE_LOG = GEP_DIR / "bridge_step2.log"

# Signal thresholds
ERRsig_THRESHOLD = 0.15  # Error rate > 15% triggers errsig
BLOAT_THRESHOLD = 50     # Avg messages > 50 triggers context_bloat
ENGAGEMENT_THRESHOLD = 0.5  # Active ratio < 50% triggers low_engagement


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(BRIDGE_LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_rtk_metrics() -> list[dict]:
    """Load RTK metrics from the JSONL file."""
    metrics = []
    if not RTK_METRICS_FILE.exists():
        log(f"WARNING: {RTK_METRICS_FILE} not found")
        return metrics
    
    with open(RTK_METRICS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                metrics.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return metrics


def load_signals() -> dict:
    """Load existing signals.json."""
    if SIGNALS_FILE.exists():
        with open(SIGNALS_FILE) as f:
            return json.load(f)
    return {"timestamp": "", "signals": [], "summary": {}}


def load_checkpoint() -> int:
    """Returns the last processed line number in rtk_metrics.jsonl."""
    if CHECKPOINT.exists():
        return int(CHECKPOINT.read_text().strip() or "0")
    return 0


def save_checkpoint(line_num: int):
    CHECKPOINT.write_text(str(line_num))


def detect_signals(metrics: dict) -> list[str]:
    """Detect evolution signals from RTK metrics."""
    signals = []
    
    error_rate = metrics.get("error_rate", 0)
    if error_rate > ERRsig_THRESHOLD:
        signals.append("errsig")
    
    sessions = metrics.get("sessions_analyzed", 0)
    if sessions > 0:
        active_ratio = metrics.get("active_sessions", 0) / sessions
        if active_ratio < ENGAGEMENT_THRESHOLD:
            signals.append("low_engagement")
        if sessions > BLOAT_THRESHOLD:
            signals.append("context_bloat")
    
    # Tool usage patterns
    tool_calls = metrics.get("tool_calls", 0)
    tokens = metrics.get("tokens_used", 0)
    if tokens > 0 and tool_calls > 0:
        efficiency = tokens / tool_calls
        if efficiency < 500:  # Low tokens per tool call
            signals.append("skill_drift")
    
    return signals


def compute_signal_score(signals: list[str]) -> float:
    """Compute overall signal score from detected signals."""
    if not signals:
        return 1.0  # No signals = healthy
    
    # Score decreases with more signals
    score = 1.0 - (len(signals) * 0.15)
    return max(0.0, min(1.0, score))


def create_evolution_event(metrics: dict, signals: list[str]) -> dict:
    """Create an EvolutionEvent from RTK metrics and detected signals."""
    signal_score = compute_signal_score(signals)
    quality_score = metrics.get("quality_score", 0.0)
    
    return {
        "type": "EvolutionEvent",
        "id": f"evt_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": "cron_analysis",
        "signals": {
            "total": len(signals),
            "types": signals,
            "overall_score": round(signal_score, 3),
        },
        "outcome": {
            "score": round(quality_score, 3),
            "sessions_analyzed": metrics.get("sessions_analyzed", 0),
            "active_ratio": round(
                metrics.get("active_sessions", 0) / max(metrics.get("sessions_analyzed", 1), 1),
                4
            ),
        },
    }


def append_event(event: dict):
    """Append an EvolutionEvent to the events.jsonl file."""
    GEP_DIR.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


def update_signals_json(signals: list[str], summary: dict):
    """Update the signals.json file."""
    GEP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Count existing events for summary
    total_events = 0
    if EVENTS_FILE.exists():
        with open(EVENTS_FILE) as f:
            total_events = sum(1 for _ in f)
    
    signals_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signals": signals,
        "summary": {
            **summary,
            "total_sessions": total_events,
        },
    }
    
    with open(SIGNALS_FILE, "w") as f:
        json.dump(signals_data, f, indent=2)


def main():
    print("=" * 60)
    log("evolver_analysis.py — START (Step 2 of 3)")
    
    # Load all RTK metrics
    all_metrics = load_rtk_metrics()
    log(f"Loaded {len(all_metrics)} RTK metrics")
    
    if not all_metrics:
        log("No RTK metrics to analyze. Done.")
        return 0
    
    # Get the latest RTK metric for analysis
    latest_metric = all_metrics[-1]
    
    # Detect signals from the latest metric
    signals = detect_signals(latest_metric)
    log(f"Detected signals: {signals if signals else 'none'}")
    
    # Create evolution event
    event = create_evolution_event(latest_metric, signals)
    append_event(event)
    log(f"Created EvolutionEvent: {event['id']}")
    
    # Update signals.json
    summary = {
        "recent_signal_score": latest_metric.get("signal_score", 0),
        "recent_quality_score": latest_metric.get("quality_score", 0),
        "recent_sessions": latest_metric.get("sessions_analyzed", 0),
        "recent_tool_calls": latest_metric.get("tool_calls", 0),
        "error_rate": latest_metric.get("error_rate", 0),
    }
    update_signals_json(signals, summary)
    log("Updated signals.json")
    
    log(f"evolver_analysis.py — DONE (Step 2 of 3)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
