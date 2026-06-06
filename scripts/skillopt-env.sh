#!/bin/bash
# SkillOpt environment setup — sources API key from Hermes config
# Usage: source ~/.hermes/scripts/skillopt-env.sh
#
# Reads ~/.hermes/config.yaml for the DeepSeek API key and sets
# the environment variables that SkillOpt's azure_openai.py expects.
# This avoids hardcoding credentials in shell history or .env files.

CONFIG="${HERMES_HOME:-$HOME/.hermes}/config.yaml"
if [ ! -f "$CONFIG" ]; then
    echo "ERROR: Hermes config not found at $CONFIG" >&2
    return 1
fi

eval "$(python3 -c "
import yaml
with open('$CONFIG') as f:
    cfg = yaml.safe_load(f)
key = cfg.get('model', {}).get('api_key', '') or ''
ep = cfg.get('model', {}).get('base_url', '')
mdl = cfg.get('model', {}).get('default', 'deepseek-v4-flash')
ep = ep.rstrip('/')
if not ep.endswith('/v1'):
    ep = ep + '/v1'
print('export AZURE_OPENAI_ENDPOINT=' + ep)
print('export AZURE_OPENAI_API_KEY=' + key)
print('export AZURE_OPENAI_AUTH_MODE=openai_compatible')
print('export OPTIMIZER_DEPLOYMENT=' + mdl)
print('export TARGET_DEPLOYMENT=' + mdl)
")" || return 1

echo "[SkillOpt] Env vars set: endpoint=$AZURE_OPENAI_ENDPOINT model=$OPTIMIZER_DEPLOYMENT"
