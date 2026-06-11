#!/usr/bin/env bash
set -euo pipefail

# Build Honcho v3 with deployment patches
# Architecture: 高内聚低耦合
#   Layer 1: honcho-api:base  — pristine v3 source (application core)
#   Layer 2: honcho-api:patched-v5  — +honcho-patch.py (deployment adaptation)
#   Layer 3: docker-compose.yml + config.toml — runtime injection (environment)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PATCH_SRC="/Users/can/.hermes/conflicting_py_bak/honcho-patch.py"

echo "=== [1/4] Copy deployment patch ==="
cp -f "$PATCH_SRC" "$SCRIPT_DIR/honcho-patch.py"

echo "=== [2/4] Build base image (pristine v3) ==="
docker build -t honcho-api:base -f "$SCRIPT_DIR/Dockerfile" "$SCRIPT_DIR"

echo "=== [3/4] Build patched overlay ==="
docker build -t honcho-api:patched-v5 \
  -f "$SCRIPT_DIR/Dockerfile.patched" "$SCRIPT_DIR"

echo "=== [4/4] Verify images ==="
docker images --filter "reference=honcho-api*" --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"

echo ""
echo "✅ Honcho images ready. Start with:"
echo "  docker compose -f $HOME/.hermes/scripts/honcho/docker-compose.yml up -d"
