#!/bin/bash
# Local persistence backup: dolt commit + workspace git commit
# Runs every 6 hours to ensure local data survives reboot

export BEADS_DIR="$HOME/.beads"
BEADS_CONFIG="$HOME/.beads/config.yaml"
WORKSPACE="$HOME/.nanobot/workspace"
LOGFILE="$HOME/.hermes/logs/local-persistence.log"

backup_dolt() {
  cd "$BEADS_DIR" || return 1
  local result
  result=$(bd dolt commit -m "auto-backup $(date '+%Y-%m-%d %H:%M:%S')" 2>&1)
  echo "$result"
  if [[ "$result" == *"Nothing to commit"* ]]; then
    return 0
  fi
}

backup_workspace() {
  cd "$WORKSPACE" || return 1
  if ! git diff --quiet || ! git diff --cached --quiet; then
    git add -A 2>/dev/null
    git commit -m "auto-backup $(date '+%Y-%m-%d %H:%M:%S')" 2>&1
  elif [ -n "$(git ls-files --others --exclude-standard)" ]; then
    git add -A 2>/dev/null
    git commit -m "auto-backup $(date '+%Y-%m-%d %H:%M:%S')" 2>&1
  else
    echo "Workspace: Nothing to commit"
  fi
}

echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "--- Dolt backup ---"
backup_dolt
echo "--- Workspace backup ---"
backup_workspace
echo "=== done ==="
