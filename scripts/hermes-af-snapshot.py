#!/usr/bin/env python3
"""
hermes-af-snapshot.py — Daily .af snapshot script for Hermes cron job.

Generates a full .af (Agent File) snapshot of the current Hermes Agent
state (config, skills with source code, memory blocks, LLM config).
Snapshots are saved to ~/.hermes/hermes-agent/agent-snapshots/
with timestamped filenames.

Keeps the 7 most recent snapshots, auto-cleans older ones.

Also performs local validation so the cron job does NOT need an LLM
call to verify the snapshot — making it resilient to API balance issues.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Use hermes-agent venv
HERMES_DIR = Path.home() / ".hermes" / "hermes-agent"
VENV_PYTHON = HERMES_DIR / "venv" / "bin" / "python3"
SNAPSHOT_DIR = HERMES_DIR / "agent-snapshots"

# Ensure SNAPSHOT_DIR exists
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Run export via hermes_af module
os.chdir(str(HERMES_DIR))

result = subprocess.run(
    [str(VENV_PYTHON), "-m", "hermes_af", "export",
     "--max-skills", "0", "--output-dir", str(SNAPSHOT_DIR)],
    capture_output=True, text=True, timeout=120
)

if result.returncode != 0:
    print(f"❌ Export failed: {result.stderr}")
    sys.exit(1)

export_line = result.stdout.strip()
print(f"✅ {export_line}")

# Parse the exported file path from stdout
# Expected format: "✅ Exported /path/to/snapshot.af (bytes)"
exported_path = None
for token in export_line.split():
    if token.endswith(".af"):
        exported_path = token
        break

if not exported_path:
    # Fallback: find the newest .af file
    snapshots = sorted(SNAPSHOT_DIR.glob("*.af"), key=os.path.getmtime, reverse=True)
    if snapshots:
        exported_path = str(snapshots[0])
    else:
        print("❌ Could not determine exported snapshot path")
        sys.exit(1)

snapshot_file = Path(exported_path)

# === Local Validation (no LLM needed) ===

errors = []

# (1) File exists and is non-empty
if not snapshot_file.exists():
    errors.append("❌ Snapshot file does not exist")
elif snapshot_file.stat().st_size == 0:
    errors.append("❌ Snapshot file is empty")
else:
    size_mb = snapshot_file.stat().st_size / (1024 * 1024)
    print(f"  ✅ File exists: {snapshot_file.name} ({size_mb:.1f} MB)")

# (2) Validate with hermes_af validate
validate_result = subprocess.run(
    [str(VENV_PYTHON), "-m", "hermes_af", "validate", str(snapshot_file)],
    capture_output=True, text=True, timeout=30
)

if validate_result.returncode == 0:
    print(f"  ✅ hermes_af validate: {validate_result.stdout.strip()}")
else:
    errors.append(f"❌ hermes_af validate failed: {validate_result.stderr.strip()}")

# (3) Get tool count for comparison
info_result = subprocess.run(
    [str(VENV_PYTHON), "-m", "hermes_af", "info", str(snapshot_file)],
    capture_output=True, text=True, timeout=30
)

tool_count = "unknown"
if info_result.returncode == 0:
    for line in info_result.stdout.splitlines():
        if "tools" in line.lower():
            import re
            m = re.search(r'(\d+)', line.split('|')[-1] if '|' in line else line)
            if m:
                tool_count = m.group(1)
                print(f"  📊 Tools: {tool_count}")
            break

# (4) Compare with previous day's snapshot
prev_snapshots = sorted(SNAPSHOT_DIR.glob("*.af"), key=os.path.getmtime, reverse=True)
if len(prev_snapshots) >= 2:
    prev_file = prev_snapshots[1]  # second newest = previous day
    prev_info = subprocess.run(
        [str(VENV_PYTHON), "-m", "hermes_af", "info", str(prev_file)],
        capture_output=True, text=True, timeout=30
    )
    if prev_info.returncode == 0:
        prev_tools = "unknown"
        for line in prev_info.stdout.splitlines():
            if "tools" in line.lower():
                import re
                m = re.search(r'(\d+)', line.split('|')[-1] if '|' in line else line)
                if m:
                    prev_tools = m.group(1)
                break
        print(f"  📊 Previous snapshot ({prev_file.name}): {prev_tools} tools")
        if tool_count != "unknown" and prev_tools != "unknown" and tool_count != prev_tools:
            print(f"  ⚠️  Tool count changed: {prev_tools} → {tool_count}")
        else:
            print(f"  ✅ Tool count stable at {tool_count}")

# Cleanup: keep only the 7 most recent snapshots
all_snapshots = sorted(SNAPSHOT_DIR.glob("*.af"), key=os.path.getmtime, reverse=True)
for old in all_snapshots[7:]:
    old.unlink()
    print(f"  🗑️  Removed old snapshot: {old.name}")

print(f"📊 Snapshots in {SNAPSHOT_DIR}: {len(all_snapshots)} total, keeping 7")

if errors:
    print("\n❌ Validation FAILED:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("\n✅ Snapshot created and validated successfully")
