#!/bin/bash
# Evolution self-check — lightweight diagnostics for cron-driven evolution
# Returns non-zero on critical failures.
# Used by: evolution-health-check cron

set -euo pipefail

EVO_DIR="/Users/can/.hermes/hermes-agent-self-evolution"
VENV_PYTHON="/Users/can/.hermes/hermes-agent/venv/bin/python"
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
    from evolution.skills.evolve_skill import evolve
    print('✅ evolution.skills.evolve_skill imported OK')
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
SKILL_COUNT=$(ls -1 /Users/can/.hermes/skills/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')
echo "✅ $SKILL_COUNT skills available"
echo ""

# 4. Run-evolution.sh dry-run test
echo "--- Dry-Run Test ---"
bash "$EVO_DIR/run-evolution.sh" --skill gif-search --iterations 1 --dry-run 2>&1 || {
    echo "⚠️  Dry-run failed (gif-search may not exist)"
    # Try with a common skill
    FIRST_SKILL=$(ls -1 /Users/can/.hermes/skills/*/SKILL.md 2>/dev/null | head -1 | xargs -I{} basename "$(dirname {})")
    if [[ -n "$FIRST_SKILL" ]]; then
        echo "   Trying with skill: $FIRST_SKILL"
        bash "$EVO_DIR/run-evolution.sh" --skill "$FIRST_SKILL" --iterations 1 --dry-run 2>&1
    fi
}

echo ""
echo "=== Self-Check Complete ==="
