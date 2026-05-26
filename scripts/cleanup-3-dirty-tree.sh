#!/bin/bash
# Dirty tree cleanup — part of the daily cleanup cascade
# cleanup-3-dirty-tree: auto-commit dirty git repos, resilient to large dirty counts
set -euo pipefail

LOG_FILE="/tmp/hermes-dirty-tree-cleanup-$(date +%Y%m%d).log"
exec >> "$LOG_FILE" 2>&1

echo "=== Dirty Tree Cleanup $(date '+%Y-%m-%d %H:%M:%S') ==="

COMMIT_MSG="chore: daily auto-commit $(date '+%Y-%m-%d')"
DIRTY_COMMITTED=0
TIMEOUT_CMD="/opt/homebrew/bin/timeout"
MAX_BULK_DIRTY=500  # If more than this many dirty files, use incremental strategy

has_remote() {
    local repo="$1"
    (cd "$repo" && git remote -v 2>/dev/null | grep -q .)
}

add_and_commit() {
    local repo="$1"
    local dirty_count="$2"

    # Strategy: for huge dirty counts (>500), avoid `git add -A` timeout
    if [ "$dirty_count" -gt "$MAX_BULK_DIRTY" ]; then
        echo "  ⚠ $repo: $dirty_count dirty files — using incremental strategy"

        # 1. Try to auto-ignore known bulky patterns first
        #    (backups/, datasets/, lancedb_data/, models/, *.lock, desktop.*)
        (cd "$repo" && git rm -r --cached backups/ 2>/dev/null) || true
        (cd "$repo" && git rm -r --cached datasets/ 2>/dev/null) || true

        # 2. Stage in batches: deleted files first (fast), then modifications
        if ! $TIMEOUT_CMD 60 git -C "$repo" add -A 2>/dev/null; then
            echo "  ⚠ $repo: 'git add -A' timed out — committing staged changes only"
        fi
    else
        cd "$repo" && git add -A 2>/dev/null
    fi

    if ! git diff --cached --quiet 2>/dev/null; then
        git commit -m "$COMMIT_MSG" 2>/dev/null
        local commit_rc=$?
        if [ $commit_rc -eq 0 ]; then
            echo "  ✓ $repo: committed $dirty_count changes"
            if has_remote "$repo"; then
                if $TIMEOUT_CMD 120 git push 2>/dev/null; then
                    echo "    ↳ pushed"
                else
                    echo "    ⚠ push timed out or failed"
                fi
            else
                echo "    ↳ skipped push (no remote configured)"
            fi
            return 0
        else
            echo "  ⚠ $repo: commit failed (exit $commit_rc)"
        fi
    fi
    return 1
}

# Find all repos under ~/.hermes
find ~/.hermes -name ".git" -type d -maxdepth 4 2>/dev/null | while read gitdir; do
    repo=$(dirname "$gitdir")

    # Skip archive and other ignored paths
    if echo "$repo" | grep -qE '\.(hermes_archive|skillclaw_backups|worktrees)(/|$)'; then
        continue
    fi

    # Skip if the .git dir itself is in an ignored path (e.g. gitignored submodule)
    if [ "$(cd "$repo" && git rev-parse --is-inside-work-tree 2>/dev/null)" != "true" ]; then
        continue
    fi

    dirty_count=$(git -C "$repo" status --porcelain 2>/dev/null | wc -l | tr -d ' ')

    if [ "$dirty_count" -gt 0 ]; then
        add_and_commit "$repo" "$dirty_count" && DIRTY_COMMITTED=$((DIRTY_COMMITTED + 1))
    fi
done

echo ""
echo "=== Dirty tree cleanup complete ==="

if [ "$DIRTY_COMMITTED" -eq 0 ]; then
    echo "[SILENT]"
else
    echo "🧹 Dirty tree: committed $DIRTY_COMMITTED repos"
fi
