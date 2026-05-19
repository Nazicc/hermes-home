#!/bin/bash
# Evolution health check — diagnostics run for the daily evolution cron
# Reports: connectivity, module imports, skill loading, environment status

set -euo pipefail

EVOLUTION_DIR="/Users/can/.hermes/hermes-agent-self-evolution"
cd "$EVOLUTION_DIR"

# Load environment
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

echo "=== Evolution Health Check ==="
echo "Timestamp: $(date -Iseconds)"
echo "Working directory: $EVOLUTION_DIR"
echo "API Base: ${OPENAI_API_BASE:-https://api.deepseek.com/v1}"
echo "Optimizer: ${EVOLUTION_OPTIMIZER_MODEL:-openai/deepseek-v4-pro}"
echo "Eval: ${EVOLUTION_EVAL_MODEL:-openai/deepseek-v4-flash}"
echo ""

# 1. Connectivity test
echo "--- Connectivity ---"
/Users/can/.hermes/hermes-agent-self-evolution-venv/bin/python3 -c "
import os, dspy
api_key = os.environ.get('DEEPSEEK_API_KEY', '')
if not api_key:
    # Try reading from .env
    env_path = os.path.expanduser('~/.hermes/.env')
    if os.path.exists(env_path):
        for line in open(env_path):
            if line.startswith('DEEPSEEK_API_KEY='):
                api_key = line.split('=', 1)[1].strip().strip('\"\\'')
                break
os.environ['OPENAI_API_KEY'] = api_key
api_base = os.environ.get('OPENAI_API_BASE', 'https://api.deepseek.com/v1')
model = os.environ.get('EVOLUTION_EVAL_MODEL', 'openai/deepseek-v4-flash')
try:
    lm = dspy.LM(model,
                  api_key=api_key,
                  api_base=api_base)
    result = lm('Reply with exactly: OK')
    print(f'✅ DSPy connectivity OK (model={model})')
    print(f'   Response: {str(result)[:80]}')
except Exception as e:
    print(f'❌ DSPy error: {e}')
"

# 2. List available skills and their sizes
echo ""
echo "--- Skill Inventory ---"
/Users/can/.hermes/hermes-agent-self-evolution-venv/bin/python3 -c "
import os, glob
skills_dir = os.path.expanduser('~/.hermes/skills')
skill_files = glob.glob(os.path.join(skills_dir, '**/SKILL.md'), recursive=True)
sizes = [(os.path.getsize(f), os.path.relpath(f, skills_dir)) for f in skill_files]
sizes.sort(reverse=True)
print(f'Total skills: {len(sizes)}')
for size, name in sizes[:10]:
    print(f'  {name}: {size:,} chars')
" 2>/dev/null || echo "⚠️  Skill inventory scan failed"

# 3. Dry-run on a small skill (via run-evolution.sh wrapper which injects API key)
echo ""
echo "--- Dry Run (small skill) ---"
bash "$EVOLUTION_DIR/run-evolution.sh" \
    --skill gif-search \
    --iterations 1 \
    --dry-run \
    2>&1 || echo "⚠️  Dry-run skipped or failed"

echo ""
echo "=== Health Check Complete ==="
