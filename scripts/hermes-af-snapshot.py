#!/usr/bin/env python3
"""
hermes-af-snapshot.py — Daily .af snapshot script for Hermes cron job.

Generates a full .af (Agent File) snapshot of the current Hermes Agent
state (config, skills with source code, memory blocks, LLM config).
Snapshots are saved to ~/.hermes/hermes-agent/agent-snapshots/
with timestamped filenames.

Keeps the 7 most recent snapshots, auto-cleans older ones.
"""

import os
import sys
import json
import glob
from pathlib import Path

# Use hermes-agent venv
HERMES_DIR = Path.home() / ".hermes" / "hermes-agent"
VENV_PYTHON = HERMES_DIR / "venv" / "bin" / "python3"
SNAPSHOT_DIR = HERMES_DIR / "agent-snapshots"

# Ensure SNAPSHOT_DIR exists
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Run export via hermes_af module
os.chdir(str(HERMES_DIR))

import subprocess
result = subprocess.run(
    [str(VENV_PYTHON), "-m", "hermes_af", "export",
     "--max-skills", "0", "--output-dir", str(SNAPSHOT_DIR)],
    capture_output=True, text=True, timeout=120
)

if result.returncode != 0:
    print(f"❌ Export failed: {result.stderr}")
    sys.exit(1)

print(f"✅ {result.stdout.strip()}")

# Cleanup: keep only the 7 most recent snapshots
snapshots = sorted(SNAPSHOT_DIR.glob("*.af"), key=os.path.getmtime, reverse=True)
for old in snapshots[7:]:
    old.unlink()
    print(f"  🗑️  Removed old snapshot: {old.name}")

print(f"📊 Snapshots in {SNAPSHOT_DIR}: {len(snapshots)} total, keeping 7")
