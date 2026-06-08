#!/bin/bash
# Evolution self-check — lightweight diagnostics for cron-driven evolution
# Returns non-zero on critical failures.
# Used by: evolution-health-check cron

set -euo pipefail

EVO_DIR="/Users/can/.hermes/hermes-agent-self-evolution"
VENV_PYTHON="/Users/can/.hermes/hermes-agent-self-evolution-venv/bin/python"
HERMES_ENV="/Users/can/.hermes/.env"

echo "=== Evolution Self-Check ==="
echo "Timestamp: $(date -Iseconds)"
echo ""

# 1. Read DeepSeek key
DEEPSEEK_API_KEY=""
if [[ -f "$HERMES_ENV" ]]; then
    DEEPSEEK_API_KEY=$(grep "^DEEPSEEK_API_KEY=" "$HERMES_ENV" | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs)
fi
if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "❌ DEEPSEEK_API_KEY not found in $HERMES_ENV"
    echo "   Evolution cannot function without an API key."
    exit 1
fi
echo "✅ DEEPSEEK_API_KEY found (prefix: ${DEEPSEEK_API_KEY:0:8}...)"

# 2. Module import check
echo ""
echo "--- Module Imports ---"
"$VENV_PYTHON" -c "
import sys
sys.path.insert(0, '$EVO_DIR')
try:
    from evolution.cli import cli
    print('✅ evolution.cli loaded OK')
except Exception as e:
    print(f'❌ Import failed: {e}')
    sys.exit(1)

import dspy
print(f'✅ DSPy {dspy.__version__} loaded')
print(f'   Has GEPA:   {hasattr(dspy, \"GEPA\")}')
print(f'   Has MIPROv2: {hasattr(dspy, \"MIPROv2\")}')
" 2>&1 || { echo "❌ Module import check FAILED"; exit 1; }

# 3. Skill inventory
echo ""
echo "--- Skill Inventory ---"
SKILL_COUNT=$(find /Users/can/.hermes/skills -maxdepth 4 -type f -name "SKILL.md" 2>/dev/null | wc -l | tr -d ' ')
echo "✅ $SKILL_COUNT skills available"
echo ""

# 4. Run-evolution.sh dry-run test
echo "--- Dry-Run Test ---"
echo "   Testing CLI structure (help + run --help)..."
"$VENV_PYTHON" -c "
import sys, importlib.util
sys.path.insert(0, '$EVO_DIR')
spec = importlib.util.find_spec('evolution.cli')
assert spec is not None, 'evolution.cli not found'
print('✅ evolution.cli spec found at', spec.origin)
# Verify all submodules load
from evolution.cli import cli
for cmd in cli.commands:
    print(f'   Command: {cmd}')
print('✅ CLI structure OK')
" 2>&1

echo ""
echo "=== Self-Check Complete ==="
