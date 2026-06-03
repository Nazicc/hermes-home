#!/bin/bash
# Hermes beads auto-snapshot script
# Periodically snapshots beads state + git pushes to GitHub
# Called by Hermes cron every 15 minutes

set -euo pipefail

REPO_DIR="$HOME/.hermes/hermes-agent"
cd "$REPO_DIR"

# Stage beads data (embedded Dolt files are tiny, < 1MB)
git add .beads/ 2>/dev/null || true

# Check if there's anything to commit
if git diff --cached --quiet .beads/ 2>/dev/null; then
    # Nothing new — stay quiet
    exit 0
fi

# Commit and push
git commit -m "chore: auto-sync beads state" --quiet 2>/dev/null || true

# Try to push — silently skip if network is down
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
if git push origin "HEAD:$CURRENT_BRANCH" 2>/dev/null; then
    echo "✅ beads state pushed to origin/$CURRENT_BRANCH"
else
    echo "⚠️  push failed (network?) — changes saved locally"
    exit 0
fi
