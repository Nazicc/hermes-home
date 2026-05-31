---
name: deerflow-mcp-integration
description: "Integrates DeerFlow as an MCP server with hermes-agent for cross-agent tool interoperability. Use when DeerFlow tools (deerflow_chat, deerflow_stream, deerflow_list_models, deerflow_list_skills, deerflow_health) are needed inside hermes-agent, when DeerFlow MCP server fails with TaskGroup errors, or when setting up/testing/debugging the DeerFlow↔hermes-agent MCP integration. NOT for: DeerFlow Docker setup, DeerFlow standalone usage, Coze Studio integration, general DeerFlow setup without MCP, or non-DeerFlow MCP servers."
category: mcp
---

## Architecture

Hermes-agent runs as a launchd service and acts as the MCP host, launching DeerFlow MCP as a stdio subprocess. DeerFlow does not run as a standalone HTTP service—it is managed entirely by hermes-agent.


hermes-agent (MCP client, Python 3.11, MCP SDK 1.27.0+)
  └── stdio_client → deerflow_mcp.py (MCP server subprocess)
  └── SkillClaw MCP proxy (port 30000)
        └── DeerFlow backend (Ollama/Minimax, port 11434)


**Important**: Inference routes through the SkillClaw proxy at `http://127.0.0.1:30000` (NOT port 1933). Port 1933 is the DeepCode backend. DeerFlow's actual backend URL should point to SkillClaw's relay.

Hermes-agent integrates multiple sub-agents via MCP:
- **DeerFlow MCP** — stdio subprocess managed by hermes-agent
- **DeepCode MCP** — httpx → :8000 backend
- **DeepTutor MCP** — httpx → :8000 backend
- **OpenViking** — port 1934 (note: not 1933!)
- **SirchMunk** — local file/directory search
- **SimpleMem** — memory/embedding search
- **SkillClaw** — MiniMax model proxy at :30000

## Prerequisites

- DeerFlow repo cloned to `~/.hermes/deer-flow-repo/`
- DeerFlow venv at `~/.hermes/deer-flow-repo/backend/.venv/`
- hermes-agent config at `~/.hermes/config.yaml`
- MCP server script at `~/.hermes/hermes-agent/mcp-servers/deerflow-mcp/deerflow_mcp.py`

## Installation

### 1. Clone DeerFlow (if not present)

bash
git clone https://github.com/ByteDance-SeedTeam/DeerFlow.git ~/.hermes/deer-flow-repo
cd ~/.hermes/deer-flow-repo/backend
uv venv .venv --python 3.12
uv pip install -e . --python .venv/bin/python


### 2. Configure in config.yaml

Add the DeerFlow MCP entry to `~/.hermes/config.yaml`:

yaml
mcp_servers:
  deerflow:
    command: /Users/can/.hermes/deer-flow-repo/backend/.venv/bin/python
    args:
      - /Users/can/.hermes/hermes-agent/mcp-servers/deerflow-mcp/deerflow_mcp.py
    env:
      DEERFLOW_CONFIG_PATH: /Users/can/.hermes/deer-flow-repo/config.yaml
      DEERFLOW_BASE_URL: http://127.0.0.1:30000  # SkillClaw proxy, NOT port 1933
      PYTHONPATH: /Users/can/.hermes/deer-flow-repo/backend/packages:${PYTHONPATH}
      MINIMAX_CN_API_KEY: ${MINIMAX_CN_API_KEY}


> **WARNING**: When archiving files from `~/.hermes/`, do NOT move `config.yaml` — it is untracked by git and belongs in the working directory. Moving it will cause hermes-agent to lose its configuration on next restart.

**Why PYTHONPATH:** The MCP server script imports from `deerflow.client`, which lives at `backend/packages/deerflow/client/` in the repo. Without this path, the import fails with `ModuleNotFoundError: No module named 'deerflow'`.

### 3. Fix MCP SDK Version Incompatibility (Critical)

hermes-agent runs MCP SDK 1.27.0+. DeerFlow's venv ships with an older MCP SDK (e.g., 1.25.0) which uses `asyncio.gather()` inside `_discover_all`. When hermes-agent already has an active anyio `TaskGroup`, this causes:


ValueError: A task in a TaskGroup must be spawned with TaskGroup.start()


**Fix:** Upgrade MCP in the DeerFlow venv to 1.28.0+:

bash
uv pip install "mcp>=1.28.0,<2.0" --python ~/.hermes/deer-flow-repo/backend/.venv/bin/python


Version 1.28.0+ changed `_discover_all` to use `anyio.create_task_group()` instead of `asyncio.gather()`, which is safe to call inside an existing TaskGroup.

## Available Tools

| Tool | Purpose |
|------|---------|
| `deerflow_chat` | Complex multi-step research with structured reflection |
| `deerflow_stream` | Streaming version of research chat |
| `deerflow_list_models` | List available Ollama/Minimax models |
| `deerflow_list_skills` | List DeerFlow's 21 built-in research skills |
| `deerflow_health` | Health check |

## MCP Dispatch Rules

| Task Type | Use This | How to Trigger |
|-----------|----------|----------------|
| Complex multi-step research, planning, creative tasks, PPT generation | **DeerFlow MCP** | `deerflow_chat` or `deerflow_stream` via hermes-agent |
| Code generation, paper-to-code, requirements analysis | **DeepCode MCP** | `deepcode_chat_planning`, `deepcode_paper_to_code` via hermes-agent |
| Tutoring, learning, knowledge base Q&A | **DeepTutor MCP** | `deeptutor_*` tools via hermes-agent |
| Local file/directory search | **SirchMunk** | `sirchmunk_*` tools |
| Memory/embedding search | **SimpleMem** | `simplemem_*` tools |

### DeepCode MCP Backend

DeepCode MCP makes httpx calls to its backend at `http://127.0.0.1:8000`:
- `deepcode_requirements_analysis` → POST with repo_url and description
- `deepcode_paper_to_code` → POST with paper_url or content
- `deepcode_workflow_status` → GET with job_id

## Common Failures

### TaskGroup Error — "A task in a TaskGroup must be spawned with TaskGroup.start()"

**Root cause:** MCP SDK version mismatch — DeerFlow venv has older MCP (<1.28.0) than hermes-agent (1.27.0+).

**Fix:**
bash
cd ~/.hermes/deer-flow-repo/backend
uv pip install "mcp>=1.28.0,<2.0" --python .venv/bin/python


### ModuleNotFoundError: No module named 'deerflow'

**Root cause:** The MCP server script's Python process cannot find the `deerflow` package because `backend/packages/` is not on the Python path.

**Fix:** Add `PYTHONPATH` to the `env` section of the MCP server entry in `config.yaml`.

### ModuleNotFoundError: No module named 'mcp'

**Root cause:** Wrong Python interpreter used (not the DeerFlow venv Python).

**Fix:** Ensure the `command` in config.yaml points to `~/.hermes/deer-flow-repo/backend/.venv/bin/python`.

### Port 1933 Connection Refused

**Root cause:** Port 1933 is DeepCode's backend, not DeerFlow. DeerFlow routes through SkillClaw at port 30000.

**Fix:** Set `DEERFLOW_BASE_URL=http://127.0.0.1:30000` in config.yaml env.

### All tools return errors or time out

1. Verify SkillClaw proxy is running: `curl http://127.0.0.1:30000/health`
2. Verify DeerFlow backend is reachable: `curl http://127.0.0.1:1933/health`
3. Check the DeerFlow config's `base_url` points to `:30000`, not `:1933`
4. Restart hermes-agent after any config change

### Other Issues

- **OpenViking port wrong**: Always use port **1934**, not 1933
- **DeepCode 422 errors**: Paper URL or repo URL format is wrong; check URL accessibility
- **SkillClaw proxy down**: Check `~/.skillclaw/health.log` for restart failures
- **DeerFlow not responding**: DeerFlow MCP is a subprocess of hermes-agent, not a standalone service

## Ports Reference

| Service | Port | Notes |
|---------|------|-------|
| hermes-gateway (SkillClaw MCP proxy) | 30000 | DeerFlow routes through here |
| OpenViking (knowledge retrieval) | 1934 | Separate service, NOT part of DeerFlow dispatch |
| DeepCode backend | 8000 | Not related to DeerFlow |
| DeerFlow backend (Ollama) | 11434 | Default Ollama port |

## Verification Checklist

bash
# 1. Check all launchd services
launchctl list | grep -E 'hermes|deerflow|openviking|skillclaw|simplemem|sirchmunk'

# 2. hermes-agent is running
curl http://127.0.0.1:8642/health

# 3. SkillClaw proxy is up
curl http://127.0.0.1:30000/health

# 4. MCP server script is executable
~/.hermes/deer-flow-repo/backend/.venv/bin/python \
  ~/.hermes/hermes-agent/mcp-servers/deerflow-mcp/deerflow_mcp.py --help

# 5. Verify DeerFlow venv MCP version
~/.hermes/deer-flow-repo/backend/.venv/bin/python -c "import mcp; print(mcp.__version__)"

# 6. Check health log
tail -30 ~/.skillclaw/health.log

# 7. DeerFlow tools appear in hermes-agent tool list
# (via hermes-agent's /v1/tools endpoint or UI)


Then restart hermes-agent to load the updated MCP configuration.

## Optional: run-deerflow.sh

bash
#!/bin/bash
set -a
source ~/.hermes/.env
set +a
exec /Users/can/.hermes/deer-flow-repo/backend/.venv/bin/python \
  /Users/can/.hermes/hermes-agent/mcp-servers/deerflow-mcp/deerflow_mcp.py

