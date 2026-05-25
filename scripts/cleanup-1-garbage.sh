#!/bin/bash
# Garbage cleanup — part of the daily cleanup cascade
# cleanup-1-garbage: temp files, cache, __pycache__, audio cache
set -euo pipefail

LOG_FILE="/tmp/hermes-garbage-cleanup-$(date +%Y%m%d).log"
exec >> "$LOG_FILE" 2>&1

echo "=== Garbage Cleanup $(date '+%Y-%m-%d %H:%M:%S') ==="

GARBAGE_COUNT=0

# Clean /tmp/hermes-* dirs >1 day old
CLEANED=$(find /tmp -maxdepth 1 -name "hermes-*" -type d -mtime +1 2>/dev/null | wc -l | tr -d ' ')
find /tmp -maxdepth 1 -name "hermes-*" -type d -mtime +1 -exec rm -rf {} + 2>/dev/null || true
GARBAGE_COUNT=$((GARBAGE_COUNT + CLEANED))
echo "  ✓ Cleaned $CLEANED temp dirs"

# Clean cache >7 days old
CLEANED=$(find ~/.hermes/cache/ -type f -mtime +7 2>/dev/null | wc -l | tr -d ' ')
find ~/.hermes/cache/ -type f -mtime +7 -delete 2>/dev/null || true
GARBAGE_COUNT=$((GARBAGE_COUNT + CLEANED))
echo "  ✓ Cleaned $CLEANED old cache files"

# Clean __pycache__
CLEANED=$(find ~/.hermes/skills -name "__pycache__" -type d -maxdepth 4 -mtime +7 2>/dev/null | wc -l | tr -d ' ')
find ~/.hermes/skills -name "__pycache__" -type d -maxdepth 4 -mtime +7 -exec rm -rf {} + 2>/dev/null || true
find ~/.hermes/skills ~/.hermes/scripts -name "*.pyc" -type f -mtime +7 -maxdepth 5 -delete 2>/dev/null || true
GARBAGE_COUNT=$((GARBAGE_COUNT + CLEANED))
echo "  ✓ Cleaned $CLEANED __pycache__ dirs"

# Clean audio cache >14 days
CLEANED=$(find ~/.hermes/audio_cache/ -type f -mtime +14 2>/dev/null | wc -l | tr -d ' ')
find ~/.hermes/audio_cache/ -type f -mtime +14 -delete 2>/dev/null || true
GARBAGE_COUNT=$((GARBAGE_COUNT + CLEANED))
echo "  ✓ Cleaned $CLEANED old audio files"

# Clean old cleanup logs
find /tmp -maxdepth 1 -name "hermes-*-cleanup-*" -type f -mtime +30 -delete 2>/dev/null || true

if [ "$GARBAGE_COUNT" -eq 0 ]; then
    echo "[SILENT]"
else
    echo "🧹 Garbage cleanup: cleaned $GARBAGE_COUNT items"
fi
