#!/bin/bash
# Session cleanup — runs as part of the daily cleanup cascade
# This is cleanup-2-sessions: delete old sessions and compress bloated ones
set -euo pipefail

LOG_FILE="/tmp/hermes-session-cleanup-$(date +%Y%m%d).log"
exec >> "$LOG_FILE" 2>&1

echo "=== Session Cleanup $(date '+%Y-%m-%d %H:%M:%S') ==="

SESSION_DELETED=0
SESSION_COMPRESSED=0
BEFORE_SIZE="N/A"
AFTER_SIZE="N/A"

# ── Delete sessions older than 90 days ──
if [ -f ~/.hermes/state.db ]; then
    BEFORE_SIZE=$(ls -lh ~/.hermes/state.db | awk '{print $5}')
    SESSION_DELETED=$(sqlite3 ~/.hermes/state.db "
        DELETE FROM sessions
        WHERE created_at < datetime('now', '-90 days');
        SELECT changes();
    " 2>/dev/null || echo "0")
    echo "  ✓ Deleted $SESSION_DELETED sessions older than 90 days"
else
    echo "  ⚠ state.db not found"
fi

# ── Compress bloated session files ──
if [ -d ~/.hermes/sessions ]; then
    for f in ~/.hermes/sessions/session_*.json; do
        [ -f "$f" ] || continue
        count=$(python3 -c "
import json
with open('$f') as fp:
    d = json.load(fp)
msgs = d.get('messages', [])
print(len(msgs))
" 2>/dev/null || echo "0")
        if [ "$count" -gt 80 ]; then
            head=5
            tail=5
            python3 -c "
import json, os, time
with open('$f') as fp:
    d = json.load(fp)
msgs = d['messages']
count = len(msgs)
d['messages'] = msgs[:$head] + [
    {'role': 'system', 'content': f'[CONTEXT COMPACTION] {count - $head - $tail} messages compressed. Original had {count} total messages.'}
] + msgs[-$tail:]
d['message_count'] = len(d['messages'])
d['_compressed_from'] = count
d['_compressed_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
with open('$f', 'w') as fp:
    json.dump(d, fp, ensure_ascii=False)
" 2>/dev/null || true
            SESSION_COMPRESSED=$((SESSION_COMPRESSED + 1))
        fi
    done
    echo "  ✓ Compressed $SESSION_COMPRESSED bloated sessions (>80 messages)"
fi

# ── Vacuum DB after deletions ──
if [ -f ~/.hermes/state.db ]; then
    sqlite3 ~/.hermes/state.db "VACUUM;" 2>/dev/null || true
    AFTER_SIZE=$(ls -lh ~/.hermes/state.db | awk '{print $5}')
    echo "  ✓ Vacuumed: ${BEFORE_SIZE} -> ${AFTER_SIZE}"
fi

echo ""
echo "=== Session cleanup complete ==="

# ── Output summary ──
SUMMARY=""
[ "$SESSION_DELETED" != "0" ] && SUMMARY="$SUMMARY deleted=$SESSION_DELETED"
[ "$SESSION_COMPRESSED" != "0" ] && SUMMARY="$SUMMARY compressed=$SESSION_COMPRESSED"
[ -n "$BEFORE_SIZE" ] && [ -n "$AFTER_SIZE" ] && [ "$BEFORE_SIZE" != "$AFTER_SIZE" ] && SUMMARY="$SUMMARY ${BEFORE_SIZE}->${AFTER_SIZE}"

if [ -z "$SUMMARY" ]; then
    echo "[SILENT]"
else
    echo "🧹 Session cleanup: $SUMMARY"
fi
