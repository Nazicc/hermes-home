#!/bin/bash
# rotate-logs.sh
# User-level log rotation for Hermes Agent & SkillClaw logs
# Runs via launchd timer (no root needed)
# Keeps max 7 compressed archives per log; archives > 10MB get compressed

set -euo pipefail

ROTATE_COUNT=7
MIN_SIZE=$((10 * 1024))  # 10KB minimum to rotate
LOG_DIRS=(
  "/Users/can/.skillclaw/logs"
  "/Users/can/.hermes/logs"
)

rotate_log() {
  local logfile="$1"
  local max_count="${2:-$ROTATE_COUNT}"

  [ -f "$logfile" ] || return 0
  [ ! -s "$logfile" ] && return 0

  local size
  size=$(stat -f%z "$logfile" 2>/dev/null || echo 0)
  [ "$size" -lt $MIN_SIZE ] && return 0

  # Rotate: shift compressed archives down (7->6, 6->5, ...)
  for i in $(seq $((max_count - 1)) -1 1); do
    local older="${logfile}.${i}.gz"
    local newer="${logfile}.$((i + 1)).gz"
    [ -f "$older" ] && mv -f "$older" "$newer"
  done

  # Compress current log
  gzip -c "$logfile" > "${logfile}.1.gz"
  : > "$logfile"
  echo "  ✓ Rotated: $(basename "$logfile") (${size} bytes → ${logfile}.1.gz)"
}

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🔄 Starting log rotation..."

for dir in "${LOG_DIRS[@]}"; do
  [ -d "$dir" ] || continue
  echo "  Directory: $dir"
  for f in "$dir"/*.log; do
    [ -f "$f" ] || continue
    # Skip already-rotated .1.gz etc
    [[ "$f" == *.gz ]] && continue
    rotate_log "$f"
  done
done

# Also prune any .gz files older than 30 days
for dir in "${LOG_DIRS[@]}"; do
  [ -d "$dir" ] || continue
  find "$dir" -name "*.gz" -mtime +30 -delete 2>/dev/null || true
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Log rotation complete"
