"""
ToolResult — Structured tool execution result dataclass.

Inspired by Claude Managed Agents' ``execute(name, input) → string`` interface.
Wraps bare string results with execution metadata so downstream consumers
(self-analysis, event logging, crash recovery) can inspect status, duration,
and error information without heuristic parsing.

Intended integration points (run_agent.py):
  - ``_run_tool()`` inner function (line ~8010): wrap _invoke_tool result
  - ``_execute_tool_calls_sequential()``: wrap per-tool result (line ~8296)
  - ``_execute_tool_calls_concurrent()`` results tuple (line ~8022)
  - Messages dict construction (line ~8164): ToolResult.to_message_dict()

Usage::

    result = ToolResult.from_output("some output", duration=1.2, name="read_file")
    msg = result.to_message_dict(tool_call_id="call_abc")
    messages.append(msg)
"""

from __future__ import annotations

import dataclasses
import json
import time
from typing import Any, Optional


@dataclasses.dataclass
class ToolResult:
    """Structured wrapper for a tool execution result.

    Fields
    ------
    output : str
        The tool's output (raw string, same as current bare result).
    status : str
        One of ``"success"``, ``"error"``, ``"cancelled"``.
    error : str | None
        Error message if status == "error".
    duration : float
        Wall-clock execution time in seconds.
    name : str | None
        Tool name (e.g. ``"terminal"``, ``"read_file"``).
    metadata : dict
        Arbitrary key-value pairs (exit code, content length, etc.).
    timestamp : float
        Unix timestamp of when this result was created.
    """

    output: str
    status: str = "success"
    error: Optional[str] = None
    duration: float = 0.0
    name: Optional[str] = None
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)
    timestamp: float = dataclasses.field(default_factory=time.time)

    # ── Factory constructors ────────────────────────────────────────────────

    @classmethod
    def from_output(
        cls,
        output: str,
        *,
        duration: float = 0.0,
        name: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ToolResult:
        """Create a successful result."""
        return cls(
            output=output,
            status="success",
            duration=duration,
            name=name,
            metadata=metadata or {},
        )

    @classmethod
    def from_error(
        cls,
        error: str,
        *,
        output: str = "",
        duration: float = 0.0,
        name: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ToolResult:
        """Create an error result."""
        return cls(
            output=output,
            status="error",
            error=error,
            duration=duration,
            name=name,
            metadata=metadata or {},
        )

    @classmethod
    def cancelled(
        cls,
        name: str,
        *,
        reason: str = "user interrupt",
    ) -> ToolResult:
        """Create a cancelled result (user interrupt / /stop)."""
        return cls(
            output=f"[Tool execution cancelled — {name} was skipped due to {reason}]",
            status="cancelled",
            error=reason,
            name=name,
        )

    # ── Serialisation ───────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict."""
        return {
            "output": self.output,
            "status": self.status,
            "error": self.error,
            "duration": self.duration,
            "name": self.name,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ToolResult:
        """Reconstruct from a dict (e.g. deserialised from JSON)."""
        return cls(
            output=d.get("output", ""),
            status=d.get("status", "success"),
            error=d.get("error"),
            duration=d.get("duration", 0.0),
            name=d.get("name"),
            metadata=d.get("metadata", {}),
            timestamp=d.get("timestamp", time.time()),
        )

    def to_message_dict(self, tool_call_id: str) -> dict[str, Any]:
        """Build the OpenAI-compatible tool message dict.

        Compatible with the existing format at run_agent.py:8164::

            tool_msg = {
                "role": "tool",
                "content": function_result,
                "tool_call_id": tc.id,
            }
        """
        msg: dict[str, Any] = {
            "role": "tool",
            "content": self.output,
            "tool_call_id": tool_call_id,
        }
        # Add structured metadata for downstream consumers (self-analysis,
        # event log, hooks). These are non-standard fields but are preserved
        # in the SQLite SessionDB messages table.
        if self.status != "success":
            msg["_tool_status"] = self.status
        if self.error:
            msg["_tool_error"] = self.error
        msg["_tool_duration"] = self.duration
        if self.name:
            msg["_tool_name"] = self.name
        return msg

    @classmethod
    def from_message_dict(cls, msg: dict[str, Any]) -> ToolResult:
        """Reconstruct from a message dict (reverse of to_message_dict)."""
        return cls(
            output=msg.get("content", ""),
            status=msg.get("_tool_status", "success"),
            error=msg.get("_tool_error"),
            duration=msg.get("_tool_duration", 0.0),
            name=msg.get("_tool_name"),
            timestamp=msg.get("timestamp", time.time()),
        )

    # ── Compatibility helpers ───────────────────────────────────────────────

    def to_5tuple(self) -> tuple[str, str, str, float, bool]:
        """Return the 5-tuple format used in run_agent.py concurrent path.

        The format is ``(function_name, function_args, result, duration, is_error)``.
        Note: ``function_args`` is a JSON string in the original; we return ``"{}"``
        here since ToolResult doesn't store args.
        """
        return (
            self.name or "",
            "{}",
            self.output,
            self.duration,
            self.status == "error",
        )

    def is_error(self) -> bool:
        return self.status == "error"

    def is_cancelled(self) -> bool:
        return self.status == "cancelled"

    def is_success(self) -> bool:
        return self.status == "success"

    def __str__(self) -> str:
        return self.output

    def __len__(self) -> int:
        return len(self.output)
