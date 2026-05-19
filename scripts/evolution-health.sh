#!/bin/bash
# Evolution health check — diagnostics run for the daily evolution cron
# Reports: connectivity, module imports, skill loading, environment status

set -euo pipefail

EVOLUTION_DIR="/Users/can/.hermes/hermes-agent/hermes-agent-self-evolution"
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
echo "API Base: $OPENAI_API_BASE"
echo "Optimizer: $EVOLUTION_OPTIMIZER_MODEL"
echo "Eval: $EVOLUTION_EVAL_MODEL"
echo ""

# 1. Connectivity test
echo "--- Connectivity ---"
/Users/can/.hermes/hermes-agent-self-evolution-venv/bin/python3 -c "
import os, dspy
os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY','')
os.environ['OPENAI_API_BASE'] = os.environ.get('OPENAI_API_BASE','')
try:
    lm = dspy.LM(os.environ.get('EVOLUTION_EVAL_MODEL', 'openai/deepseek-v4-flash'),
                  api_key=os.environ['OPENAI_API_KEY'],
                  api_base=os.environ['OPENAI_API_BASE'])
    result = lm('Ping')
    print('✅ DSPy connectivity OK')
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

# 3. Dry-run on a small skill
echo ""
echo "--- Dry Run (small skill) ---"
/Users/can/.hermes/hermes-agent-self-evolution-venv/bin/python3 -m evolution.skills.evolve_skill \
    --skill gif-search \
    --iterations 1 \
    --dry-run \
    2>&1 || echo "⚠️  Dry-run skipped or failed"

echo ""
echo "=== Health Check Complete ==="
