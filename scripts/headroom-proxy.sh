#!/bin/bash
# Headroom proxy launcher — used by launchd plist
# Sources ~/.hermes/.env for API keys, then starts the proxy.
set -e
exec 2>&1  # stderr → stdout so both go to same log

cd /Users/can  # headroom creates ./.headroom DB in cwd

echo "[$(date)] Sourcing .env..."
set +e                    # tolerate non-fatal .env errors (Chrome path, etc.)
source /Users/can/.hermes/.env 2>/dev/null
set -e

# Ensure PATH includes the venv
export PATH="/Users/can/.hermes/hermes-agent/venv/bin:$PATH"

# Headroom binary in the same venv
HEADROOM="/Users/can/.hermes/hermes-agent/venv/bin/headroom"

echo "[$(date)] Starting headroom proxy..."

exec "$HEADROOM" proxy \
  --memory \
  --learn \
  --code-aware \
  --code-graph \
  --mode token
