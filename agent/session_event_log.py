"""
SessionEventLog — Append-only event log for Hermes Agent sessions.

Inspired by Claude Managed Agents' ``emitEvent(sessionId, event)`` pattern.
Each session gets a JSONL file at ``~/.hermes/sessions/events/<sessionId>.jsonl``.

Event types
-----------
- ``system`` — Session start/stop, configuration
- ``tool_call`` — A tool was invoked (name + args)
- ``tool_result`` — A tool returned (name + duration + status)
- ``brain_invoke`` — An LLM API call was initiated
- ``brain_response`` — An LLM API call completed
- ``session_compression`` — Context compression occurred
- ``user_message`` — User input received

Design principles (from CMA)::

    emitEvent(id, event)     — append-only, no mutations
    getEvents(offset, limit) — slice the event stream
    wake(sessionId)          — reconstruct session from last known event

Current state: emit() + replay() implemented.
getEvents() and wake() are stubs for Step 3.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional


# ── Event types ─────────────────────────────────────────────────────────────

EVENT_TYPES = frozenset({
    "system",
    "tool_call",
    "tool_result",
    "brain_invoke",
    "brain_response",
    "session_compression",
    "user_message",
})


# ── Event dataclass ─────────────────────────────────────────────────────────

class SessionEvent:
    """A single event in the session event stream.

    Parameters
    ----------
    type : str
        One of EVENT_TYPES.
    payload : dict
        Event-specific data.
    timestamp : float
        Unix timestamp (auto-generated if omitted).
    """

    __slots__ = ("type", "payload", "timestamp")

    def __init__(
        self,
        event_type: str,
        payload: dict[str, Any],
        timestamp: Optional[float] = None,
    ):
        if event_type not in EVENT_TYPES:
            raise ValueError(
                f"Unknown event type {event_type!r}. "
                f"Valid types: {sorted(EVENT_TYPES)}"
            )
        self.type = event_type
        self.payload = payload
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SessionEvent:
        return cls(
            event_type=d["type"],
            payload=d.get("payload", {}),
            timestamp=d.get("timestamp"),
        )

    def __repr__(self) -> str:
        return f"<SessionEvent {self.type} @ {self.timestamp:.3f}>"


# ── Event log writer / reader ──────────────────────────────────────────────

class SessionEventLog:
    """Append-only event log for a single session.

    Thread-safe: uses a per-instance lock for writes.

    Parameters
    ----------
    session_id : str
        Unique session identifier (e.g. UUID).
    log_dir : str | Path
        Directory for JSONL event files. Defaults to
        ``~/.hermes/sessions/events/``.
    """

    def __init__(
        self,
        session_id: str,
        log_dir: Optional[str | Path] = None,
    ):
        self.session_id = session_id
        if log_dir is None:
            log_dir = Path.home() / ".hermes" / "sessions" / "events"
        else:
            log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = log_dir / f"{session_id}.jsonl"
        self._lock = threading.Lock()

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def log_path(self) -> Path:
        return self._log_path

    @property
    def exists(self) -> bool:
        return self._log_path.exists()

    # ── Write ─────────────────────────────────────────────────────────────

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> SessionEvent:
        """Emit an event to the append-only log.

        Thread-safe.
        """
        event = SessionEvent(event_type, payload)
        with self._lock:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def emit_tool_call(
        self,
        name: str,
        args: dict[str, Any],
        tool_call_id: str,
    ) -> SessionEvent:
        """Convenience: emit a tool_call event."""
        return self.emit("tool_call", {
            "name": name,
            "args": args,
            "tool_call_id": tool_call_id,
        })

    def emit_tool_result(
        self,
        name: str,
        duration: float,
        status: str,
        error: Optional[str] = None,
        output_length: int = 0,
    ) -> SessionEvent:
        """Convenience: emit a tool_result event."""
        payload: dict[str, Any] = {
            "name": name,
            "duration": duration,
            "status": status,
            "output_length": output_length,
        }
        if error:
            payload["error"] = error
        return self.emit("tool_result", payload)

    def emit_brain_invoke(
        self,
        model: str,
        messages_count: int,
        tokens_estimate: int,
    ) -> SessionEvent:
        """Emit a brain_invoke event (LLM API call start)."""
        return self.emit("brain_invoke", {
            "model": model,
            "messages_count": messages_count,
            "tokens_estimate": tokens_estimate,
        })

    def emit_brain_response(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration: float,
        finish_reason: Optional[str] = None,
    ) -> SessionEvent:
        """Emit a brain_response event (LLM API call end)."""
        return self.emit("brain_response", {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration": duration,
            "finish_reason": finish_reason,
        })

    def emit_compression(
        self,
        before_messages: int,
        before_tokens: int,
        after_messages: int,
        after_tokens: int,
        strategy: str = "summary",
    ) -> SessionEvent:
        """Emit a session_compression event."""
        return self.emit("session_compression", {
            "before_messages": before_messages,
            "before_tokens": before_tokens,
            "after_messages": after_messages,
            "after_tokens": after_tokens,
            "strategy": strategy,
        })

    # ── Read ──────────────────────────────────────────────────────────────

    def replay(self) -> list[SessionEvent]:
        """Read all events for this session (full event stream)."""
        if not self._log_path.exists():
            return []
        events: list[SessionEvent] = []
        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    events.append(SessionEvent.from_dict(d))
                except (json.JSONDecodeError, KeyError, ValueError):
                    # Skip corrupted lines
                    continue
        return events

    def get_events(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> list[SessionEvent]:
        """Get a slice of the event stream.

        Parameters
        ----------
        offset : int
            Number of events to skip from the beginning.
        limit : int | None
            Max events to return. ``None`` means all remaining.

        Returns
        -------
        list[SessionEvent]
            The requested slice of events.

        Note
        ----
        Currently reads the full log and slices in memory.
        For large logs, a future version could seek to the offset line
        directly using a pre-built index.
        """
        all_events = self.replay()
        if offset >= len(all_events):
            return []
        end = offset + limit if limit is not None else None
        return all_events[offset:end]

    def count_events(self) -> int:
        """Count total events without loading them all into memory."""
        if not self._log_path.exists():
            return 0
        count = 0
        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    # ── Reconstruction / Wake ─────────────────────────────────────────────

    def wake(self) -> list[SessionEvent]:
        """Reconstruct session events from the last checkpoint onwards.

        **Step 3 stub.** Currently delegates to ``replay()``.
        Future: read events from last checkpoint, rebuild messages[].
        """
        return self.replay()

    # ── Diagnostics ───────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return summary statistics for this event log."""
        events = self.replay()
        type_counts: dict[str, int] = {}
        total_duration = 0.0
        for ev in events:
            type_counts[ev.type] = type_counts.get(ev.type, 0) + 1
            if ev.type == "tool_result":
                total_duration += ev.payload.get("duration", 0.0)

        return {
            "session_id": self.session_id,
            "exists": self._log_path.exists(),
            "total_events": len(events),
            "event_types": type_counts,
            "first_event_timestamp": events[0].timestamp if events else None,
            "last_event_timestamp": events[-1].timestamp if events else None,
            "total_tool_duration": total_duration,
            "avg_tool_duration": (
                total_duration / type_counts.get("tool_result", 1)
                if type_counts.get("tool_result", 0) > 0 else 0.0
            ),
        }
