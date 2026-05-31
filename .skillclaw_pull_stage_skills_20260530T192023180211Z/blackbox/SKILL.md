---
name: blackbox
description: "Use when delegating coding tasks to the Blackbox AI CLI agent (`npx blackbox`) or when launching/using the HKUDS DeepCode multi-agent code engine (port 8000 backend, port 5173 frontend) and DeepTutor agentic learning system (port 8001 backend, port 3782 frontend) at /Users/can/DeepCode. DeepTutor is a git submodule nested inside DeepCode at /Users/can/DeepCode/DeepTutor. NOT for: general terminal commands, file operations, or Python scripts without code-generation context."
category: general
---

# Blackbox AI CLI + HKUDS DeepCode + DeepTutor

Delegate coding tasks to Blackbox AI via terminal. Covers three related systems:

1. **Blackbox AI CLI** — Generic multi-model coding agent (`npx blackbox`)
2. **DeepCode** — HKUDS multi-agent code generation engine at `/Users/can/DeepCode`
3. **DeepTutor** — Agentic learning system, git submodule inside DeepCode

---

## Prerequisites

- **Blackbox CLI**: `npx blackbox` (requires Node.js 20+)
- **DeepCode** at `/Users/can/DeepCode`
- **DeepTutor** submodule at `/Users/can/DeepCode/DeepTutor`
- **MiniMax LLM backend** at `https://api.minimaxi.com/anthropic/v1` (configured in `mcp_agent.secrets.yaml`)
- **sirchmunk MCP server** for local embedding cache
- **deepcode-hku** pip package for research-to-code pipeline

---

## When to Use

- Long-running autonomous coding sessions requiring multi-model judgment
- Tasks benefiting from iterative AI code review cycles
- Research paper-to-code transformations via deepcode-hku pipeline
- DeepTutor-backed agentic learning workflows

## When NOT to Use

- One-liner edits or trivial changes
- Tasks requiring tight iteration loops (use direct tools instead)
- General shell commands, file browsing, or non-code-generation tasks
- When opencode CLI is preferred for a specific task

---

## Service Ports

| Service   | Backend | Frontend |
|-----------|---------|----------|
| DeepCode  | 8000    | 5173     |
| DeepTutor | 8001    | 3782     |

---

## Quick Start

### 1. Check if services are already running

bash
lsof -i :8000  # DeepCode backend
lsof -i :5173  # DeepCode frontend
lsof -i :8001  # DeepTutor backend
lsof -i :3782  # DeepTutor frontend
curl -s http://127.0.0.1:8000/health


**If backend is healthy, do NOT restart it.** Only start missing frontends.

### 2. Start DeepCode

bash
cd /Users/can/DeepCode
./run.sh   # starts backend :8000 + frontend :5173


Or start components individually:

bash
# Backend
cd /Users/can/DeepCode && python -m mcp_agent.run &

# Frontend
cd /Users/can/DeepCode/new_ui/frontend && npm run dev &


**Config**: `/Users/can/DeepCode/mcp_agent.secrets.yaml`

**API Key**: MiniMax API key at `https://api.minimaxi.com/anthropic/v1`

### 3. Start DeepTutor

bash
cd /Users/can/DeepCode/DeepTutor
cp .env.example .env
# Edit .env with LLM_API_KEY, EMBEDDING_API_KEY, LLM_BASE_URL=https://api.minimaxi.com/anthropic/v1
pip install -e ".[server]" -q
python -m deeptutor.server --port 8001


**Alternative**: `python -m deeptutor_cli run` (launches backend :8001 + frontend :3782)

**Status**: `curl http://127.0.0.1:8001/health` → `{"status":"healthy"}`

### 4. Via deepcode-hku Pipeline

bash
pip install deepcode-hku
deepcode-hku transform --paper /path/to/paper.pdf --output ./generated/


---

## Blackbox AI CLI

Blackbox is a multi-model coding agent CLI that dispatches tasks to multiple LLMs and uses a judge to select the best implementation.

### Setup

bash
npm install -g blackboxai  # or: npm install -g @blackboxai/cli
npx blackbox configure     # configure API key from https://app.blackbox.ai/dashboard


### Basic Usage

bash
# Interactive mode
npx blackbox

# One-shot task
npx blackbox --task "implement feature X"

# With model selection
npx blackbox --model gpt-4


### One-Shot Tasks

**Always use `pty=true`** for Blackbox CLI — interactive terminal apps will hang without a PTY:

bash
terminal(command="npx blackbox --task 'Add JWT authentication with refresh tokens to the Express API'", workdir="/path/to/project", pty=true)


### Background Mode (Long Tasks)

For tasks that take minutes, use background mode:

bash
# Start in background with PTY
terminal(command="npx blackbox --task 'Refactor the auth module to use OAuth 2.0'", workdir="~/project", background=true, pty=true)
# Returns session_id

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Send input if Blackbox asks a question
process(action="submit", session_id="<id>", data="yes")

# Kill if needed
process(action="kill", session_id="<id>")


### Checkpoints & Resume

bash
# After a task completes, Blackbox shows a checkpoint tag
terminal(command="npx blackbox --resume-checkpoint 'task-abc123' --task 'Now add rate limiting'", workdir="~/project", pty=true)


### Session Commands

| Command   | Effect                       |
|-----------|------------------------------|
| `/compress` | Shrink conversation history |
| `/clear` | Wipe history and start fresh |
| `/stats` | View current token usage     |
| `Ctrl+C` | Cancel current operation      |

### PR Reviews

Clone to a temp directory to avoid modifying the working tree:

bash
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && npx blackbox --task 'Review this PR against main.'", pty=true)


### Parallel Work

bash
terminal(command="npx blackbox --task 'Fix the login bug'", workdir="/tmp/issue-1", background=true, pty=true)
terminal(command="npx blackbox --task 'Add unit tests for auth'", workdir="/tmp/issue-2", background=true, pty=true)
process(action="list")


### Key Flags

| Flag | Effect |  
|------|--------|
| `--task "task"` | Non-interactive one-shot execution |
| `--resume-checkpoint "tag"` | Resume from a saved checkpoint |
| `--yolo` | Auto-approve all actions and model switches |
| `--model <name>` | Specify a model |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Port 8000 not responding | `cd /Users/can/DeepCode && python -m mcp_agent.run` |
| Port 8000 already in use | Kill existing process: `lsof -ti:8000 | xargs kill` |
| Port 5173 not responding | Check vite dev server in `new_ui/frontend/` |
| Frontend not loading | Check `/tmp/deepcode_frontend.log` for errors |
| DeepTutor returns error | Set `LLM_API_KEY` in `/Users/can/DeepCode/DeepTutor/.env` to the actual MiniMax key |
| DeepTutor import fails | Run `pip install -e ".[server]"` from DeepTutor dir |
| MiniMax API errors | Verify `mcp_agent.secrets.yaml` has valid `api_key` |
| SSL errors on model download | Use `simplemem-local-embedding` skill for sirchmunk cache fallback |

---

## Rules

1. **Always use `pty=true`** for Blackbox CLI — interactive terminal apps will hang without a PTY
2. **Use `workdir`** — keep the agent focused on the right directory
3. **Background for long tasks** — use `background=true` and monitor with `process` tool
4. **Don't interfere** — monitor with `poll`/`log`, don't kill sessions because they're slow
5. **Report results** — after completion, check what changed and summarize for the user
6. **Credits cost money** — Blackbox uses a credit-based system; multi-model mode consumes credits faster

---

## Related Skills

- `opencode` — Alternative CLI agent for coding delegation
- `deepcode-deeptutor-launch` — Specific skill for launching DeepCode/DeepTutor services
- `deepcode-research-engine` — Research paper to code pipeline
- `simplemem-local-embedding` — Local embedding with HuggingFace SSL bypass
