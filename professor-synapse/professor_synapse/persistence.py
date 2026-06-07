"""
Persistence — crash-safe checkpointing for session state.

Pattern (proven in evolution/persistence.py):
  1. Write to temp file
  2. fsync the file
  3. fsync the parent directory
  4. Rename temp → final (atomic on same filesystem)

Sentinel fallback: when a checkpoint is incomplete (crash mid-write),
detect via missing/malformed .sentinel file and fall back to
last-known-good checkpoint or fresh start.
"""

from __future__ import annotations
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from professor_synapse.state import RunState


class CheckpointManager:
    """
    Manages atomic checkpoint read/write for RunState.

    Directory layout:
      <base_dir>/
        checkpoints/
          <session_id>/
            state.json        # Latest completed checkpoint
            state.json.tmp    # In-progress write (should not exist)
            .sentinel         # Marker: write completed successfully
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).expanduser().resolve()
        self._ckpt_dir = self.base_dir / "checkpoints"
        self._ckpt_dir.mkdir(parents=True, exist_ok=True)

    # ── Helpers ──────────────────────────────────────────────

    def _session_dir(self, session_id: str) -> Path:
        d = self._ckpt_dir / session_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _state_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "state.json"

    def _tmp_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "state.json.tmp"

    def _sentinel_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / ".sentinel"

    @staticmethod
    def _fsync(path: Path) -> None:
        """Force data to disk. macOS needs fd-level fsync."""
        fd = os.open(path, os.O_WRONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        """fsync the parent directory for atomic rename safety."""
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    # ── Public API ────────────────────────────────────────────

    def save(self, state: RunState) -> None:
        """
        Atomically save a RunState checkpoint.

        Three-step protocol:
          1. Write JSON to .tmp
          2. fsync file + dir
          3. Rename .tmp → .json (atomic on same filesystem)
          4. Write .sentinel marker
        """
        session_id = state.session.session_id
        tmp = self._tmp_path(session_id)
        final = self._state_path(session_id)

        # Step 1: write to temp
        tmp.write_text(state.as_json(), encoding="utf-8")

        # Step 2: fsync
        self._fsync(tmp)
        self._fsync_dir(tmp.parent)

        # Step 3: atomic rename
        tmp.replace(final)
        self._fsync(final)
        self._fsync_dir(final.parent)

        # Step 4: sentinel marker
        sentinel = self._sentinel_path(session_id)
        sentinel.write_text("OK\n", encoding="utf-8")
        self._fsync(sentinel)
        self._fsync_dir(sentinel.parent)

    def load(self, session_id: str) -> Optional[RunState]:
        """
        Load a checkpoint. Returns None if:
          - No state file exists (fresh session)
          - Sentinel is missing (crash mid-write — discard incomplete state)
        """
        state_file = self._state_path(session_id)
        sentinel = self._sentinel_path(session_id)

        if not state_file.exists():
            return None

        # Sentinel check: if missing, the last write crashed
        if not sentinel.exists():
            self._cleanup_incomplete(session_id)
            return None

        try:
            raw = state_file.read_text(encoding="utf-8")
            return RunState.from_json(raw)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            # Corrupted file — treat as incomplete
            self._cleanup_incomplete(session_id)
            return None

    def _cleanup_incomplete(self, session_id: str) -> None:
        """Remove all files for a session that crashed mid-write."""
        sess_dir = self._session_dir(session_id)
        if sess_dir.exists():
            shutil.rmtree(sess_dir)

    def delete_session(self, session_id: str) -> None:
        """Remove all checkpoint data for a session."""
        sess_dir = self._session_dir(session_id)
        if sess_dir.exists():
            shutil.rmtree(sess_dir)

    def list_sessions(self) -> list[str]:
        """Return all session IDs that have valid checkpoints."""
        if not self._ckpt_dir.exists():
            return []
        sessions = []
        for entry in self._ckpt_dir.iterdir():
            if entry.is_dir() and (entry / ".sentinel").exists():
                sessions.append(entry.name)
        return sorted(sessions)

    def clear_all(self) -> None:
        """Remove ALL checkpoint data. Use with extreme caution."""
        if self._ckpt_dir.exists():
            shutil.rmtree(self._ckpt_dir)
            self._ckpt_dir.mkdir(parents=True, exist_ok=True)
