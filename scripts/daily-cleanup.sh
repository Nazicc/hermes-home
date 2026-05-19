#!/bin/bash
# Daily cleanup — runs at 4:00 AM
# Cleans: garbage files, old sessions, dirty git trees, stale caches
set -euo pipefail

LOG_FILE="/tmp/hermes-daily-cleanup-$(date +%Y%m%d).log"

# Save original stdout for the summary line
exec 3>&1
# All verbose output goes to log file
exec >> "$LOG_FILE" 2>&1

echo "=== Hermes Daily Cleanup $(date '+%Y-%m-%d %H:%M:%S') ==="

SUMMARY=""
GARBAGE_COUNT=0
SESSION_DELETED=0
SESSION_SIZE="N/A"
DIRTY_COMMITTED=0

# ── 1. 垃圾清理 ──
echo "[1/4] Cleaning garbage files..."

# 清理 /tmp/hermes-* 临时目录（超过 1 天）
TMP_CLEANED=$(find /tmp -maxdepth 1 -name "hermes-*" -type d -mtime +1 2>/dev/null | wc -l | tr -d ' ')
find /tmp -maxdepth 1 -name "hermes-*" -type d -mtime +1 -exec rm -rf {} + 2>/dev/null || true
GARBAGE_COUNT=$((GARBAGE_COUNT + TMP_CLEANED))
echo "  ✓ Cleaned $TMP_CLEANED temp dirs"

# 清理 ~/.hermes/cache/ 旧缓存（超过 7 天）
CACHE_CLEANED=$(find ~/.hermes/cache/ -type f -mtime +7 2>/dev/null | wc -l | tr -d ' ')
find ~/.hermes/cache/ -type f -mtime +7 -delete 2>/dev/null || true
GARBAGE_COUNT=$((GARBAGE_COUNT + CACHE_CLEANED))
echo "  ✓ Cleaned $CACHE_CLEANED old cache files"

# 清理 Python __pycache__
PYC_CLEANED=$(find ~/.hermes/skills -name "__pycache__" -type d -maxdepth 4 -mtime +7 2>/dev/null | wc -l | tr -d ' ')
find ~/.hermes/skills -name "__pycache__" -type d -maxdepth 4 -mtime +7 -exec rm -rf {} + 2>/dev/null || true
# 只扫描 skills 和 scripts 下的 .pyc
find ~/.hermes/skills ~/.hermes/scripts -name "*.pyc" -type f -mtime +7 -maxdepth 5 -delete 2>/dev/null || true
GARBAGE_COUNT=$((GARBAGE_COUNT + PYC_CLEANED))
echo "  ✓ Cleaned $PYC_CLEANED __pycache__ dirs"

# 清理 audio cache（超过 14 天）
AUDIO_CLEANED=$(find ~/.hermes/audio_cache/ -type f -mtime +14 2>/dev/null | wc -l | tr -d ' ')
find ~/.hermes/audio_cache/ -type f -mtime +14 -delete 2>/dev/null || true
GARBAGE_COUNT=$((GARBAGE_COUNT + AUDIO_CLEANED))
echo "  ✓ Cleaned $AUDIO_CLEANED old audio files"

# 清理旧日志
find /tmp -maxdepth 1 -name "hermes-daily-cleanup-*" -type f -mtime +30 -delete 2>/dev/null || true

echo ""

# ── 2. Session 清理 ──
echo "[2/4] Cleaning old sessions..."

if [ -f ~/.hermes/state.db ]; then
    BEFORE_SIZE=$(ls -lh ~/.hermes/state.db | awk '{print $5}')
    SESSION_DELETED=$(sqlite3 ~/.hermes/state.db "
        DELETE FROM sessions
        WHERE created_at < datetime('now', '-90 days');
        SELECT changes();
    " 2>/dev/null || echo "0")
    echo "  ✓ Deleted $SESSION_DELETED sessions older than 90 days"

    sqlite3 ~/.hermes/state.db "VACUUM;" 2>/dev/null || true
    AFTER_SIZE=$(ls -lh ~/.hermes/state.db | awk '{print $5}')
    SESSION_SIZE="${BEFORE_SIZE}->${AFTER_SIZE}"
    echo "  ✓ Vacuumed: $SESSION_SIZE"
else
    echo "  ⚠ state.db not found"
fi

echo ""

# ── 3. 脏树清理 ──
echo "[3/4] Auto-committing dirty git trees..."

COMMIT_MSG="chore: daily auto-commit $(date '+%Y-%m-%d')"

find ~/.hermes -name ".git" -type d -maxdepth 4 2>/dev/null | while read gitdir; do
    repo=$(dirname "$gitdir")
    cd "$repo"

    if echo "$repo" | grep -q ".hermes_archive"; then
        continue
    fi

    dirty_count=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    if [ "$dirty_count" -gt 0 ]; then
        if [ "$repo" = "$HOME/.hermes" ] || [ "$repo" = "$HOME/.hermes/hermes-agent" ] || [ "$repo" = "$HOME/.hermes/hermes-agent-self-evolution" ]; then
            git add -A 2>/dev/null
            if ! git diff --cached --quiet 2>/dev/null; then
                git commit -m "$COMMIT_MSG" 2>/dev/null && echo "  ✓ $repo: committed $dirty_count changes" || echo "  ⚠ $repo: commit failed"
                git push 2>/dev/null && echo "    ↳ pushed" || echo "    ⚠ push failed"
            fi
        else
            echo "  ⚠ $repo: $dirty_count dirty files (needs review)"
        fi
    fi
done

# Count committed repos
DIRTY_COMMITTED=$(grep -c "committed" "$LOG_FILE" 2>/dev/null || echo "0")

echo ""

# ── 4. 上下文清理 ──
echo "[4/4] Cleaning stale contexts..."

CTX_CLEANED=0
if [ -d ~/.hermes/logs ]; then
    C=$(find ~/.hermes/logs -type f -mtime +30 2>/dev/null | wc -l | tr -d ' ')
    find ~/.hermes/logs -type f -mtime +30 -delete 2>/dev/null || true
    CTX_CLEANED=$((CTX_CLEANED + C))
    echo "  ✓ Cleaned $C old log files"
fi

# 清理 context compressor 缓存
C=$(find ~/.hermes/ -maxdepth 4 -name "compressed_*.json" -type f -mtime +30 2>/dev/null | wc -l | tr -d ' ')
find ~/.hermes/ -maxdepth 4 -name "compressed_*.json" -type f -mtime +30 -delete 2>/dev/null || true
CTX_CLEANED=$((CTX_CLEANED + C))
echo "  ✓ Cleaned $C compressed contexts"

# 清理 trajectory 数据（超过 60 天）
C=$(find ~/.hermes/ -maxdepth 5 -path "*/trajectories/*" -type f -mtime +60 2>/dev/null | wc -l | tr -d ' ')
find ~/.hermes/ -maxdepth 5 -path "*/trajectories/*" -type f -mtime +60 -delete 2>/dev/null || true
CTX_CLEANED=$((CTX_CLEANED + C))
echo "  ✓ Cleaned $C old trajectories"

echo ""
echo "=== Cleanup complete ==="

# ── Summary to stdout (this becomes the cron delivery) ──
exec 1>&3 2>/dev/null || true
exec 3>&- 2>/dev/null || true

SUMMARY="🧹 每日清理 ($(date '+%m/%d %H:%M'))"
[ "$SESSION_DELETED" != "0" ] && SUMMARY="$SUMMARY | session: -${SESSION_DELETED}条"
[ "$SESSION_SIZE" != "N/A" ] && SUMMARY="$SUMMARY | DB: $SESSION_SIZE"
[ "$DIRTY_COMMITTED" != "0" ] && SUMMARY="$SUMMARY | 提交脏树"
[ "$((GARBAGE_COUNT + CTX_CLEANED))" -gt 0 ] && SUMMARY="$SUMMARY | 清理 $((GARBAGE_COUNT + CTX_CLEANED)) 项"

if [ "$SESSION_DELETED" = "0" ] && [ "$DIRTY_COMMITTED" = "0" ] && [ "$((GARBAGE_COUNT + CTX_CLEANED))" = "0" ]; then
    echo "[SILENT]"
else
    echo "$SUMMARY"
fi
