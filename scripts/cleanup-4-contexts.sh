#!/bin/bash
# Context cleanup — part of the daily cleanup cascade
# cleanup-4-contexts: stale logs, compressed contexts, old trajectories
set -euo pipefail

LOG_FILE="/tmp/hermes-context-cleanup-$(date +%Y%m%d).log"
exec >> "$LOG_FILE" 2>&1

echo "=== Context Cleanup $(date '+%Y-%m-%d %H:%M:%S') ==="

CTX_CLEANED=0

# Clean old log files (>30 days)
if [ -d ~/.hermes/logs ]; then
    C=$(find ~/.hermes/logs -type f -mtime +30 2>/dev/null | wc -l | tr -d ' ')
    find ~/.hermes/logs -type f -mtime +30 -delete 2>/dev/null || true
    CTX_CLEANED=$((CTX_CLEANED + C))
    echo "  ✓ Cleaned $C old log files"
fi

# Clean compressed context cache (>30 days)
C=$(find ~/.hermes/ -maxdepth 4 -name "compressed_*.json" -type f -mtime +30 2>/dev/null | wc -l | tr -d ' ')
find ~/.hermes/ -maxdepth 4 -name "compressed_*.json" -type f -mtime +30 -delete 2>/dev/null || true
CTX_CLEANED=$((CTX_CLEANED + C))
echo "  ✓ Cleaned $C compressed contexts"

# Clean trajectory data (>60 days)
C=$(find ~/.hermes/ -maxdepth 5 -path "*/trajectories/*" -type f -mtime +60 2>/dev/null | wc -l | tr -d ' ')
find ~/.hermes/ -maxdepth 5 -path "*/trajectories/*" -type f -mtime +60 -delete 2>/dev/null || true
CTX_CLEANED=$((CTX_CLEANED + C))
echo "  ✓ Cleaned $C old trajectories"

echo ""
echo "=== Context cleanup complete ==="

if [ "$CTX_CLEANED" -eq 0 ]; then
    echo "[SILENT]"
else
    echo "🧹 Context cleanup: cleaned $CTX_CLEANED items"
fi
