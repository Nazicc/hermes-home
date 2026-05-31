---
name: deerflow-hermes-integration
description: "Integrate ByteDance DeerFlow multi-agent research framework with hermes-agent via MCP, and route its capabilities through hermes-agent's OpenAI-compatible API Server. Covers: MCP stdio integration, asyncio event-loop considerations (including anyio TaskGroup nesting), Docker vs K8s deployment behavior, Coze Studio OpenAPI 3.0 passthrough, and per-user context isolation."
category: general
---

## Architecture Overview

[DeerFlow MCP Server] ←→ [hermes-agent stdio MCP client] ←→ [OpenAI-compatible API /v1/mcp/deerflow/*]
                                       ↓
                             [Feishu / Lark inbound]
                             [SkillClaw skill routing]

DeerFlow is ByteDance's open-source multi-agent research framework built on LangGraph. When integrated with hermes-agent via MCP, requests flow:


hermes-agent (MCP client)
  → MCP stdio (deerflow-mcp server, langgraph callback)
    → DeerFlow LangGraph workflow (web search, browsing, coding agents)
      → Results returned to hermes via MCP tool calls


- **DeerFlow** (`bytedance/deerflow`): Multi-agent research framework. Exposes an MCP-compatible stdio interface internally.
- **hermes-agent** (`hermes-agent`): Receives requests via Feishu inbound webhooks, calls MCP tools via stdio, returns structured results.
- **OpenAI-compatible API** (`hermes-agent` built-in server): Exposes DeerFlow MCP tools at `/v1/mcp/deerflow/` for external callers (e.g., Claude Desktop, OpenRouter).
- **SkillClaw**: Routes skill-selection requests to hermes-agent based on task description matching against skill `description` fields.

## DeerFlow Deployment Modes

### Docker Compose Mode (Local)

bash
cd ~/deerflow
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
docker compose up -d

# Verify the gateway is up:
curl -s http://localhost:8080/health | python3 -m json.tool
# → {"status": "healthy"}


**Expected behavior**: The `provisioner` container will restart in a loop. This is **NORMAL and expected** — the provisioner container is designed for Kubernetes (K8s) API connectivity and attempts to connect to a K8s API at `host.docker.internal:26443`. In Docker compose mode (without K8s), this connection fails and the container restarts continuously. This does NOT indicate a problem and does NOT affect the other services.

Verify the main services are healthy:
bash
docker compose ps
# Should show: nginx, frontend, gateway, langgraph — all running (not restarting)

# Health check
curl -s http://localhost:8080/health
# → {"status": "healthy"}


The web UI is accessible at `http://localhost:8000` when Docker mode is active.

### Kubernetes Mode

For K8s deployments, ensure the K8s API is accessible at the configured endpoint and the provisioner has the appropriate service account credentials.

## MCP Server Discovery and Initialization

hermes-agent discovers and initializes MCP servers in `tools/mcp_tool.py` via `_discover_and_register_servers()` and `_discover_and_register_server()`. Each server is initialized asynchronously using `_safe_init()`.

### Locate the MCP Server Command

DeerFlow does not ship a standalone MCP server binary. The MCP server is the DeerFlow Python process itself, invoked with a subcommand:

bash
# Option A: Via Python module (preferred for subprocess mode)
python -m deerflow.server.mcp

# Option B: Via npm package (if installed)
npx deerflow-mcp

# Verify the actual entrypoint:
cd ~/deerflow
python -c "import deerflow.server.mcp; print(deerflow.server.mcp.__file__)"
# → ~/deerflow/deerflow/server/mcp.py


## Critical: Asyncio Event-Loop Constraints

### ⚠️ anyio TaskGroup Nesting in `_safe_init`

**Problem**: `_safe_init()` uses `asyncio.gather()` to initialize multiple MCP server components concurrently. When hermes-agent itself is already running inside an existing anyio `TaskGroup` (e.g., when handling an incoming request), calling `asyncio.gather()` inside `_safe_init` causes an `asyncio.gather() was never awaited` error and results in the MCP server failing to initialize silently. The error manifests as:


unhandled errors in a TaskGroup
asyncio.run() cannot be called from a running event loop


**Symptom**: The deerflow-mcp toolset fails to load with no tools from it appearing in the tool list. Check `~/.hermes/logs/agent.log` for "TaskGroup" errors around MCP initialization.

**Workarounds** (in order of preference):

1. **Run the MCP server as a separate subprocess** (recommended):
   yaml
   mcp_servers:
     deerflow:
       enabled: true
       command: /Users/can/.venv/bin/python
       args:
         - -m
         - deerflow.server.mcp
       cwd: /Users/can/deerflow
       env:
         DEERFLOW_ENV: production
         LOG_LEVEL: INFO
   

2. **Disable in config and access via native API** (if TaskGroup nesting cannot be fixed):
   yaml
   mcp:
     servers:
       deerflow:
         enabled: false  # Disable MCP, use Docker API instead
   
   Then access DeerFlow via its native API at `http://localhost:8000`.

When writing custom wrappers around DeerFlow:
- Prefer `async def` with `await` for all async operations
- Avoid `asyncio.run()` in any code path reachable from hermes-agent's async stack
- If you must bridge sync and async code, use `asyncio.get_event_loop().run_in_executor()`
- For nested async work, use `asyncio.new_event_loop()` + `loop.run_until_complete()` or migrate to the TaskGroup API

## hermes-agent Configuration

### config.yaml MCP Server Entry

yaml
mcp_servers:
  deerflow:
    enabled: true
    command: python
    args:
      - -m
      - deerflow.server.mcp
    cwd: /Users/can/deerflow
    env:
      DEERFLOW_HOST: "http://host.docker.internal:8000"
      # Or for native access (no Docker):
      # DEERFLOW_HOST: "http://127.0.0.1:8000"
      DEERFLOW_ENV: production
      LOG_LEVEL: INFO
    # Optional: timeout per tool call (ms)
    timeout_ms: 60000


Or using npx (if using the npm package):

yaml
mcp_servers:
  deerflow-mcp:
    enabled: true
    command: npx
    args: ["deerflow-mcp"]
    env:
      DEERFLOW_API_KEY: "${DEERFLOW_API_KEY}"


### OpenAI-Compatible API Server Routing

yaml
server:
  base_url: "http://127.0.0.1:30000/v1"
  provider: custom  # Do not change — required for SkillClaw routing


## Restart hermes-agent

bash
# Find the hermes-agent process
ps aux | grep hermes-agent | grep -v grep

# Send SIGHUP to reload config (or restart the service)
kill -HUP <pid>

# Or via launchd if managed by launchd:
launchctl kickstart -k gui/$(id -u)/com.hermes-agent
launchctl load ~/Library/LaunchAgents/com.hermes-agent.plist


## Verify MCP Tools Are Loaded

bash
# Check hermes-agent logs
tail -f ~/.hermes/logs/agent.log | grep -i "deerflow\|mcp"

# List available tools via the hermes-agent API
curl -s http://127.0.0.1:30000/v1/tools | python3 -m json.tool
# The deerflow tools should appear under the "deerflow" namespace


## Routing via hermes-agent API Server

### DeerFlow → hermes-agent (Upstream)

DeerFlow can call hermes-agent's OpenAI-compatible endpoint to use hermes-agent tools as part of a DeerFlow research session:

python
from openai import OpenAI

client = OpenAI(
    api_key="hermes-agent-api-key",
    base_url="http://localhost:8000/v1"  # hermes-agent API server
)

response = client.chat.completions.create(
    model="deerflow/research",
    messages=[{"role": "user", "content": "Research the impact of AI on coding productivity"}],
    tools=[...],  # hermes-agent tool definitions
    tool_choice="auto"
)


### hermes-agent → DeerFlow (Downstream)

hermes-agent can delegate web research, multi-step planning, or document synthesis to DeerFlow by calling the DeerFlow MCP tools (registered as hermes-agent tools via the deerflow-mcp stdio server):

python
# Via hermes-agent MCP tool invocation (automatic when deerflow-mcp is registered)
result = await ctx.tools.deerflow_mcp.research(
    query="AI coding assistant benchmarks 2024",
    depth="deep",
    sources=["web", "arxiv"]
)


## Coze Studio OpenAPI 3.0 Passthrough

If routing Coze Studio bots through DeerFlow:

python
# deerflow/plugins/coze_studio.py
import httpx

class CozeStudioPassthrough:
    """Proxy Coze Studio OpenAPI 3.0 calls through DeerFlow for tool call routing."""

    BASE_URL = "https://api.coze.com/v1"

    def __init__(self, api_key: str):
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def chat(self, bot_id: str, user_message: str) -> dict:
        payload = {
            "bot_id": bot_id,
            "user_id": "hermes-agent",
            "query": user_message,
            "stream": False,
        }
        resp = await self.client.post("/chat", json=payload)
        resp.raise_for_status()
        return resp.json()


For Coze Studio proxies using OpenAPI 3.0:

python
# Override base URL for Coze Studio
client = OpenAI(
    api_key="${COZE_API_KEY}",
    base_url="https://private-latest.coze.cn/open_api/v2",
    default_headers={"Authorization": "Bearer ${COZE_API_KEY}"}
)

# Map hermes-agent tool calls to Coze bot IDs
TOOL_TO_BOT_MAP = {
    "web_search": "bot_deerflow_search",
    "document_summarize": "bot_deerflow_summarize",
    "code_generation": "bot_deerflow_code",
}


If DeerFlow is accessed via Coze Studio's OpenAPI 3.0 endpoint, route through hermes-agent's gateway:

yaml
coze_studio:
  base_url: "https://api.coze.cn/v1"
  api_key: "${COZE_API_KEY}"
  workflow_id: "${DEERFLOW_WORKFLOW_ID}"


## Per-User Context Isolation

DeerFlow supports multi-user research sessions. When invoked from hermes-agent, always pass the Feishu/Lark user ID as the `user_id` parameter to ensure context isolation:

python
SESSION_DIR = Path(f"/tmp/deerflow-sessions/{user_id}")
CONFIG_PATH = SESSION_DIR / "config.yaml"
CONTEXT_PATH = SESSION_DIR / "context.json"

SESSION_DIR.mkdir(parents=True, exist_ok=True)

async def call_deerflow(user_id: str, query: str) -> dict:
    return await coze_passthrough.chat(
        bot_id=DEERFLOW_BOT_ID,
        user_message=f"[user_id={user_id}] {query}",
    )


DeerFlow supports per-user context isolation via session tags:
python
session_tag = f"user:{user_id}"
# Pass to DeerFlow via MCP tool call metadata


**Guidelines:**
- Store per-user DeerFlow API keys in the session directory, not global config
- Pass `user_id` to all DeerFlow tool calls to maintain conversation history
- Clean up sessions on logout or after a TTL

## Diagnostic Commands

bash
# Check DeerFlow Docker services status
docker compose -f ~/deerflow/docker-compose.yml ps

# Check hermes-agent MCP server logs
grep -i "deerflow\|TaskGroup\|MCP" ~/.hermes/logs/agent.log | tail -20

# Health check (SkillClaw proxy + Hermes routing)
bash ~/.hermes/skillclaw-health.sh
cat ~/.skillclaw/health.log

# Verify DeerFlow web UI is accessible
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000


## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `"unhandled errors in a TaskGroup"` in agent.log | DeerFlow MCP server uses nested asyncio in `_safe_init()` | Run as subprocess (see workaround above) or disable in config.yaml |
| deerflow-mcp toolset empty or silent | MCP server process not started | Verify `deerflow` in mcp_servers config and check subprocess logs |
| DeerFlow tools not in `/v1/tools` list | hermes-agent not restarted after config change | `kill -HUP <pid>` or restart service |
| MCP connection refused | DeerFlow container not fully started | `docker compose up -d && sleep 5` |
| Provisioner container always restarting | Expected in Docker mode | Ignore; core services are healthy |
| `curl localhost:8080/health` returns 000 | DeerFlow not running | `docker compose restart gateway` |
| DeerFlow API 401 errors | Wrong API key or base_url | Confirm base_url points to hermes-agent API, not DeerFlow's internal server |
| Browser automation fails | Playwright not installed or no sandbox | Run `playwright install` and ensure sandbox permissions |
| Per-user context bleeding | Missing user_id in session paths | Always include user_id in SESSION_DIR and CONFIG_PATH |

## Dependencies

- DeerFlow: `pip install deerflow` or Docker Compose
- hermes-agent MCP tool support: anyio, asyncio
- Optional: LangGraph for custom workflow extensions
