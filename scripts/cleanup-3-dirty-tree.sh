#!/bin/bash
# Dirty tree cleanup — part of the daily cleanup cascade
# cleanup-3-dirty-tree: auto-commit dirty git repos
set -euo pipefail

LOG_FILE="/tmp/hermes-dirty-tree-cleanup-$(date +%Y%m%d).log"
exec >> "$LOG_FILE" 2>&1

echo "=== Dirty Tree Cleanup $(date '+%Y-%m-%d %H:%M:%S') ==="

COMMIT_MSG="chore: daily auto-commit $(date '+%Y-%m-%d')"
DIRTY_COMMITTED=0

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
                DIRTY_COMMITTED=$((DIRTY_COMMITTED + 1))
            fi
        else
            echo "  ⚠ $repo: $dirty_count dirty files (needs review)"
        fi
    fi
done

echo ""
echo "=== Dirty tree cleanup complete ==="

if [ "$DIRTY_COMMITTED" -eq 0 ]; then
    echo "[SILENT]"
else
    echo "🧹 Dirty tree: committed $DIRTY_COMMITTED repos"
fi
