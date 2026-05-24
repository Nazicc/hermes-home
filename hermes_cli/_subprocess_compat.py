"""
Subprocess compatibility shims.

Restored stub: original module shipped in newer hermes_cli releases but
absent from this checkout. process_registry.py and environments/local.py
import ``windows_hide_flags`` and only invoke it on Windows; on POSIX it
must return 0 (the test suite asserts this).
"""
from __future__ import annotations

import sys


def windows_hide_flags() -> int:
    """Return CREATE_NO_WINDOW on Windows so spawned subprocesses don't
    flash a console window; return 0 elsewhere (no-op for Popen)."""
    if sys.platform == "win32":
        try:
            import subprocess
            return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        except Exception:
            return 0x08000000
    return 0
