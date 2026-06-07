"""
Session — lifecycle management for orchestration sessions.

Handles: create → route → serve → advance → close.

Each step is checkpointed. If the process crashes, load()
returns the last completed checkpoint and the conductor
can resume from there.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from professor_synapse.state import RunState, SessionState
from professor_synapse.persistence import CheckpointManager


class Session:
    """
    A persisted orchestration session.

    Usage:
        session = Session.create("/tmp/ckpt", intent="分析最新漏洞")
        state = session.state
        # ... conductor does its work ...
        session.save()
    """

    def __init__(self, state: RunState, checkpointer: CheckpointManager) -> None:
        self.state = state
        self._ckpt = checkpointer

    @classmethod
    def create(
        cls,
        base_dir: str | Path,
        intent: str = "",
        phase: str = "init",
    ) -> Session:
        ckpt = CheckpointManager(base_dir)
        state = RunState(
            phase=phase,
            session=SessionState.create(intent=intent),
        )
        ckpt.save(state)
        return cls(state=state, checkpointer=ckpt)

    @classmethod
    def load_or_create(
        cls,
        base_dir: str | Path,
        session_id: Optional[str] = None,
        intent: str = "",
    ) -> Session:
        """
        Load existing session or create a new one.

        If session_id is given, try to load that specific session.
        Otherwise, load the most recent session or create fresh.
        """
        ckpt = CheckpointManager(base_dir)

        if session_id:
            state = ckpt.load(session_id)
            if state is not None:
                return cls(state=state, checkpointer=ckpt)

        # Try most recent session
        sessions = ckpt.list_sessions()
        if sessions and not session_id:
            latest = sessions[-1]
            state = ckpt.load(latest)
            if state is not None and not state.completed:
                return cls(state=state, checkpointer=ckpt)

        # Create fresh
        return cls.create(base_dir, intent=intent)

    def save(self) -> None:
        """Persist current state atomically."""
        self._ckpt.save(self.state)

    def advance(self, phase: str) -> None:
        """Move to next phase and checkpoint."""
        self.state.phase = phase
        self.state.session.advance_turn()
        self.save()

    def close(self) -> None:
        """Mark as completed and persist."""
        self.state.completed = True
        self.save()

    @property
    def session_id(self) -> str:
        return self.state.session.session_id
