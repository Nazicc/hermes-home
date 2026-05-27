#!/bin/bash
# Context cleanup — part of the daily cleanup cascade
# cleanup-4-contexts: stale logs, compressed contexts, old trajectories
set -euo pipefail

LOG_FILE="/tmp/hermes-context-cleanup-$(date +%Y%m%d).log"
exec >> "$LOG_FILE" 2>&1

echo "=== Context Cleanup $(date '+%Y-%m-%d %H:%M:%S') ==="

CTX_CLEANED=0

# ── Step 1: Old log files (>30 days) ──
if [ -d ~/.hermes/logs ]; then
    C=$(find ~/.hermes/logs -type f -mtime +30 2>/dev/null | wc -l | tr -d ' ')
    find ~/.hermes/logs -type f -mtime +30 -delete 2>/dev/null || true
    CTX_CLEANED=$((CTX_CLEANED + C))
    echo "  ✓ Cleaned $C old log files"
fi

# ── Step 2: Compressed context cache (>30 days) ──
# Quick-existence check first — saves traversing 88K files when none exist
if [ -d ~/.hermes/sessions ]; then
    if find ~/.hermes/sessions -maxdepth 2 -name "compressed_*.json" -type f -print -quit 2>/dev/null | grep -q .; then
        C=$(find ~/.hermes/sessions -maxdepth 2 -name "compressed_*.json" -type f -mtime +30 2>/dev/null | wc -l | tr -d ' ')
        find ~/.hermes/sessions -maxdepth 2 -name "compressed_*.json" -type f -mtime +30 -delete 2>/dev/null || true
    else
        C=0
    fi
else
    C=0
fi
CTX_CLEANED=$((CTX_CLEANED + C))
echo "  ✓ Cleaned $C compressed contexts"

# ── Step 3: Trajectory data (>60 days) ──
# Only scan known trajectory directories — avoids full-tree find that hangs
TRAJ_DIRS=""
for candidate in "$HOME/.hermes/trajectories" "$HOME/.hermes/sessions/trajectories" "$HOME/.hermes/data/trajectories"; do
    [ -d "$candidate" ] && TRAJ_DIRS="${TRAJ_DIRS}${TRAJ_DIRS:+ }${candidate}"
done
if [ -z "$TRAJ_DIRS" ]; then
    C=0
else
    C=0
    for d in $TRAJ_DIRS; do
        count=$(find "$d" -type f -mtime +60 2>/dev/null | wc -l | tr -d ' ')
        find "$d" -type f -mtime +60 -delete 2>/dev/null || true
        C=$((C + count))
    done
fi
CTX_CLEANED=$((CTX_CLEANED + C))
echo "  ✓ Cleaned $C old trajectories"

echo ""
echo "=== Context cleanup complete ==="

if [ "$CTX_CLEANED" -eq 0 ]; then
    echo "[SILENT]"
else
    echo "🧹 Context cleanup: cleaned $CTX_CLEANED items"
fi
