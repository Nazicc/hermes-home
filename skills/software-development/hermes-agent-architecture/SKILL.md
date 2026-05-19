---
name: hermes-agent-architecture
description: "Hermes Agent 项目架构 — cli.py、run_agent.py、HermesCLI、AIAgent 的关系，hermes mcp 子命令、MCP 服务器配置与迁移(Gateway/Dashboard 端口)、state.db 内部诊断、MemoryProvider Plugin→MCP Server 解耦迁移流程、以及如何正确添加新命令和 handlers。Use when modifying Hermes codebase, managing MCP server connections, debugging gateway startup, understanding the CLI-to-Agent relationship, reading hermes internal state, OR migrating tools from Plugin to MCP Server. NOT for: general agent usage (use hermes-agent skill), writing agent prompts, or managing skills (those have their own skills)."
category: general
---

## Project Structure Overview


hermes-agent/
├── cli.py                  # CLI entry point, HermesCLI class
├── run_agent.py            # Agent runtime core, AIAgent class
├── gateway/                # Gateway server (HTTP API + MCP client)
│   └── run.py              # Gateway HTTP server
├── agent/
│   └── skill_commands.py   # /skill-name command routing
│   ├── tool_result.py      # ★ CMA-inspired: structured ToolResult dataclass (status, duration, error, metadata)
│   └── session_event_log.py# ★ CMA-inspired: append-only JSONL event log (session_start/end, tool_call/result, brain_invoke/response, compression)
├── tools/
│   └── skills_tool.py      # SKILL.md parsing + tool registration
├── cron/
│   └── scheduler.py        # Scheduled task dispatcher
├── mcp-servers/            # MCP server implementations (git-tracked)
├── skills/                 # Built-in skills
└── tests/                 # Test suite


## Architecture Diagram


hermes (CLI entry) → cli.py → run_agent.py → AIAgent → Tools/Skills/MCP


## HermesCLI and AIAgent Relationship


cli.py → HermesCLI (CLI interface)
             ↓ calls
run_agent.py → AIAgent (Agent runtime)
                     ↓
               Gateway (MCP client + HTTP API, port 8642)
                     ↓ spawns
               MCP servers (stdio subprocesses, managed by Gateway)


**Key constraint**: MCP server implementations must be placed in `hermes-agent/mcp-servers/` and version-controlled via git. Placing them elsewhere in `~/.hermes/` will not persist across repo clone/sync.

## CLI Entry Points

The hermes CLI is installed at `~/.hermes/hermes-agent/venv/bin/hermes`.

bash
hermes --help
hermes chat model gateway setup whatsapp login logout auth status cron webhook doctor dump debug backup import config pairing skills plugins memory tools mcp sessions insights claw version update ...


Key commands:
- `hermes chat` — interactive chat session (default)
- `hermes mcp` — MCP server management
- `hermes gateway` — run the Hermes Gateway (TUI/gateway daemon)
- `hermes doctor` — health diagnostics
- `hermes skills` — skill management
- `hermes config` — view/edit config

## Runtime Modes

Hermes Agent has two runtime modes:
- **CLI mode**: `hermes chat`, `hermes tui`, `hermes cron`, etc. via `cli.py`
- **Gateway mode**: Long-running HTTP/API server via `gateway/run.py`, port 8642 (internal), Dashboard on 9119

The Gateway is the MCP server host — it spawns MCP servers as stdio subprocesses and manages their lifecycle.

## Process Model

| Process | Startup | Responsibility |
|---------|---------|----------------|
| **Gateway** | launchd plist (`RunAtLoad=true`, `KeepAlive=true`) | Main entry, schedules all Agents and MCP Servers |
| **Cron/Scheduled Agent** | hermes-agent internal scheduler or system cron | Independent scheduled tasks |
| **MCP Servers** | **Spawned by Gateway as subprocesses via stdio** | Tool providers |
| **SkillClaw** | Direct npx launch (not launchd) | API routing proxy |

**Do NOT create independent launchd plists for MCP servers** — MCP servers are children of the Gateway, terminating when Gateway terminates.

## Config File

Primary config: `~/.hermes/config.yaml`

**Key sections:**
yaml
mcp_servers:
  <name>:
    command: <cmd>
    args: [<args...>]
    env:
      KEY: VALUE
    cwd: /path/to/working/directory
providers:
  # LLM provider configuration
llm:
  # LLM settings
gateway:
  # Gateway startup options
skills:
  external_dirs:
    - /path/to/external/skills


## hermes mcp Subsystem

Hermes has a built-in MCP client supporting stdio and HTTP transport modes.

### Subcommand Reference

bash
hermes mcp --help           # View all subcommands
hermes mcp list             # List configured MCP servers
hermes mcp add <name> --command <cmd> --args <args...>  # Add stdio MCP server
hermes mcp add <name> --url <endpoint>                  # Add HTTP MCP server
hermes mcp add <name> --command <cmd> --args <args...> --env KEY=VALUE  # With env vars
hermes mcp remove <name>    # Remove
hermes mcp test <name>      # Test connection
hermes mcp serve            # Expose Hermes as MCP server
hermes mcp configure        # Interactive configuration
hermes mcp login            # Authentication


### Adding stdio Mode MCP Servers

**Example — sirchmunk:**
bash
hermes mcp add sirchmunk --command sirchmunk --args mcp serve --env SIRCHMUNK_WORK_PATH=/Users/can/.hermes/sirchmunk-data


**Example — DeerFlow:**
bash
hermes mcp add deerflow --command python3 --args -m deerflow.mcp.server --env DEERFLOW_DATA_PATH=/Users/can/.hermes/deerflow-data


**Example — HTTP MCP server:**
bash
hermes mcp add <name> --url http://localhost:PORT/mcp


**Confirm success:**
bash
hermes mcp list
# Output: Name | Transport | Tools | Status
# sirchmunk  sirchmunk mcp serve  all  ✓ enabled


**Bypassing interactive prompts for scripting:**
bash
echo "Y" | hermes mcp add sirchmunk --command sirchmunk --args mcp serve --env SIRCHMUNK_WORK_PATH=/Users/can/.hermes/sirchmunk-data


### Adding a New MCP Server Steps

1. Write MCP server implementation (Python class + `@mcp_server.listens()` decorator, or use `fastmcp`)
2. **Important**: Place MCP server code in `~/.hermes/hermes-agent/mcp-servers/`
3. Update `~/.hermes/config.yaml` `mcp_servers` node, pointing to repo-relative path:

yaml
mcp_servers:
  myserver:
    command: /Users/can/.hermes/hermes-agent/venv/bin/python
    args: ["-m", "mcp_servers.myserver", "serve"]


4. Verify:
bash
hermes mcp add myserver --command <cmd> --args <args...>
hermes mcp list          # Confirm status = enabled
hermes mcp test myserver # Test connection


### Sirchmunk MCP Config Reference

The `hermes mcp add` command writes server definitions to `~/.hermes/config.yaml`. Example from `~/.hermes/sirchmunk-data/mcp_config.json`:


{
  "mcpServers": {
    "sirchmunk": {
      "command": "sirchmunk",
      "args": ["mcp", "serve"],
      "env": {
        "SIRCHMUNK_SEARCH_PATHS": "",
        "SIRCHMUNK_WORK_PATH": "/Users/can/.hermes/sirchmunk-data"
      }
    }
  }
}


## MCP Server Lifecycle

When creating MCP adapters for services that expose REST APIs:

1. The service (e.g., DeepCode on `:8000`, DeepTutor on `:8001`) must be running separately as an HTTP server.
2. Create an MCP adapter script that calls the service's REST endpoints and exposes them as MCP tools.
3. Add with `hermes mcp add <name> --command python3 --args <adapter_script.py>`.
4. Alternatively, for HTTP-based MCP servers, use `hermes mcp add <name> --url <http-url>`.

## MCP Server Implementation Storage

MCP server implementations should live inside the hermes-agent repo under `hermes-agent/mcp-servers/` and be committed to git. This ensures reproducibility — a fresh clone or restart restores all MCP functionality without manual setup.

| Directory | Description | Tool Count |
|-----------|-------------|------------|
| `mcp-servers/deerflow-mcp/` | DeerFlow FastMCP adapter | 1+ |
| `mcp-servers/deepcode-mcp/` | DeepCode REST→MCP adapter | 9 |
| `mcp-servers/deeptutor-mcp/` | DeepTutor REST→MCP adapter | 23 |
| `mcp-servers/sirchmunk/` | Sirchmunk search MCP server | — |

## Gateway Ports

| Port | Service |
|------|---------|
| 8642 | Gateway HTTP API (internal) |
| 9119 | Gateway Dashboard |

**Health check:**
bash
curl -s http://localhost:8642/health


## Gateway Launch Mechanism

Gateway managed via launchd user service:

bash
# Service name
com.hermes-agent.gateway

# Check status
launchctl list | grep hermes

# Manual load/unload
launchctl load ~/Library/LaunchAgents/com.hermes-agent.gateway.plist
launchctl unload ~/Library/LaunchAgents/com.hermes-agent.gateway.plist

# Logs
tail -f ~/.hermes/logs/gateway.log


## Launchd Services

Only two launchd services should be persisted independently:
- `io.hermes.sirchmunk` — Sirchmunk MCP search server (KeepAlive)
- Hermes Gateway itself (may be launched as a user agent)

MCP servers are spawned as stdio subprocesses by the Gateway — they should NOT be independently daemonized.

## state.db — Authoritative Metrics Source

**Path**: `~/.hermes/state.db` (not session JSON files)

Session JSON files (`~/.hermes/sessions/`) contain message text only, not token counts or end_reason. Use state.db for metrics queries.

### Schema

**sessions table:**
- `id` (TEXT PRIMARY KEY)
- `name` (TEXT)
- `model` (TEXT)
- `input_tokens` / `output_tokens` (INTEGER)
- `tool_call_count` (INTEGER)
- `compression_count` (INTEGER)
- `end_reason` (TEXT) — 'stop'|'max_tokens'|'error'|'success'|'compression'|'cron_complete'|'max_turns'
- `created_at` / `updated_at` / `finished_at` (REAL — Unix timestamp)

**messages table:**
- `id` (TEXT PRIMARY KEY)
- `session_id` (TEXT, FK)
- `role` (TEXT) — 'user'|'assistant'|'tool'
- `content` (TEXT)
- `tool_call_name` / `tool_call_args` / `tool_call_result` (TEXT)
- `is_compression` (INTEGER)
- `exit_code` (INTEGER) — tool execution status
- `created_at` (REAL)

### Diagnostic Query Examples

python
import sqlite3
from datetime import datetime, timezone, timedelta

tz_bj = timezone(timedelta(hours=8))
now = datetime.now(tz_bj)
cutoff = now - timedelta(hours=4)

db = sqlite3.connect("/Users/can/.hermes/state.db")
cur = db.cursor()

# Recent N hours session aggregation
cur.execute("""
    SELECT 
        COUNT(*),
        SUM(input_tokens + output_tokens),
        SUM(tool_call_count)
    FROM sessions
    WHERE created_at > ?
""", (cutoff.timestamp(),))

# end_reason distribution
cur.execute("SELECT end_reason, COUNT(*) FROM sessions GROUP BY end_reason")

# Compression events (context compaction)
cur.execute("""
    SELECT m.session_id, substr(m.content, 1, 100)
    FROM messages m
    WHERE m.content LIKE '%CONTEXT COMPACTION%'
    AND m.created_at > ?
""", (cutoff.timestamp(),))

# Tool errors (non-zero exit code)
cur.execute("""
    SELECT session_id, substr(content, 1, 80), exit_code
    FROM messages
    WHERE exit_code != 0 AND exit_code IS NOT NULL
    AND created_at > ?
    ORDER BY created_at DESC
    LIMIT 20
""", (cutoff.timestamp(),))

# Compression events
cur.execute("""
    SELECT session_id, COUNT(*)
    FROM messages
    WHERE is_compression = 1
    GROUP BY session_id
"""

# Recent sessions with metrics
cur.execute("""
    SELECT id, start_time, end_time, end_reason, input_tokens, output_tokens
    FROM sessions
    ORDER BY start_time DESC LIMIT 10
""")


## Skills System

### Storage Locations

- **Built-in skills**: `~/.hermes/hermes-agent/skills/<category>/`
- **User skills**: `~/.hermes/skills/skills/<skill-name>/`
- **Runtime registration**: `~/.hermes/config.yaml` `skills` node

### Discovery Path (priority high to low)

1. `~/.hermes/skills/<name>/SKILL.md`
2. `~/.hermes/hermes-agent/skills/<category>/<name>/SKILL.md`

Each skill is a directory containing `SKILL.md` (with YAML frontmatter).

### Matching Mechanism

Skills are matched by front-matter YAML headers:
- `name` — skill name
- `description` — SkillClaw routing trigger
- `trigger` — keyword list (optional)
- `anti_trigger` — reverse match keywords (optional)

### Built-in Diagnostic Skills

- `hermes-diagnostics` — Query state.db for health reports
- `hermes-agent` — CLI usage, configuration, spawning agents
- `hermes-atropos-environments` — gateway/deployment environments
- `mcporter` — Manage MCP servers via mcporter CLI
- `native-mcp` — hermes-agent built-in MCP client usage

## Adding New Commands Correctly

**When adding CLI subcommands**: Use `@cli.command()` in `cli.py`'s `HermesCLI` class. Business logic goes in `run_agent.py`'s `AIAgent`, or create a new module under `agent/`. **Do not put business logic directly in cli.py — delegate to AIAgent.**

1. Create `*_commands.py` in `hermes_agent/cli/` or `hermes_agent/gateway/`, reference `agent/skill_commands.py`
2. Register new command as AIAgent tool or CLI subcommand
3. Update `cli.py` `build_parser()` and `gateway/run.py` routing
4. Write tests: `tests/cli/test_*.py` or `tests/gateway/test_*.py`

## Configuration File Locations

| File | Path |
|------|------|
| Main config | `~/.hermes/config.yaml` |
| Environment variables | `~/.hermes/.env` |
| Session data | `~/.hermes/sessions/` |
| Skills | `~/.hermes/skills/skills/` |
| Hermes Agent source | `~/.hermes/hermes-agent/` |
| MCP servers (repo-tracked) | `~/.hermes/hermes-agent/mcp-servers/` |
| Memory | `~/.hermes/memories/` |
| state.db | `~/.hermes/state.db` |
| Sirchmunk data | `~/.hermes/sirchmunk-data/` |
| Gateway logs | `~/.hermes/logs/gateway.log` |
| Sirchmunk daemon | `~/Library/LaunchAgents/com.hermes.sirchmunk.plist` |

## When NOT to use this skill

- **General Hermes usage** → use `hermes-agent` skill
- **MCP server debugging** → use `mcp-debugging` skill
- **Evolver integration** → use `hermes-evolver-integration` skill
- **SimpleMem MCP setup** → use `simplemem-integration` skill
- **Skill evolution** → use `skills-evolution-from-research` skill

## Reference Files

- `references/mcp-migration-concrete.md` — Step-by-step guide for migrating tools from MemoryProvider Plugin to standalone MCP Server. Covers: MCP server creation pattern (FastMCP→REST HTTP), Plugin slimming (keep only lifecycle hooks), config.yaml registration, end-to-end testing with `ClientSession`, and pitfalls (.env quoting, stream API, atexit race).
- `references/codegraph-mcp-setup.md` — CodeGraph MCP server setup: npm install, WASM SQLite index init (300s timeout), stale `.codegraph/` cleanup before re-init, `--path` config requirement, JSON-RPC echo verification.
- `references/agent-loop-internals.md` — Agent runtime internals: run_conversation() flow, tool execution pipeline, session persistence (SQLite schema), context compression, hook system. Essential reference when modifying the agent loop, tool dispatch, or session persistence code.

## Memory System Architecture & Coupling Analysis

### MemoryProvider Plugin Architecture

Hermes's memory system has **three distinct coupling paths** to external memory services (OpenViking, TDB-AM, etc.):

| Path | Interface | Stability | Risk |
|------|-----------|-----------|------|
| **MemoryProvider ABC** (Plugin) | `get_tool_schemas()`, `handle_tool_call()` | 🔴 Hermes-version-coupled | ABC changes break tool registration |
| **MCP Tools** (MCP protocol) | JSON-RPC 2.0 via stdio/HTTP | 🟢 Protocol-stable | Survives Hermes upgrades |
| **Direct REST** (HTTP API) | HTTP client in Plugin | 🟢 Network-stable | Survives Hermes upgrades |

### Tool Registration Flow (Current — Fragile)

```
Plugin.get_tool_schemas()
    ↓ returns list of dict schemas
MemoryManager._tool_to_provider[tool_name] = provider
    ↓ registered in dispatch table
AIAgent.setup() — appends schemas to self.tools (run_agent.py:2079-2093)
    ↓ tool schemas sent to LLM
LLM calls tool → memory_manager.has_tool(name)? → handle_tool_call(name, args)
```

**Breaks when Hermes upgrades**:
- `get_tool_schemas()` signature changes (return type, arg format)
- `handle_tool_call()` signature changes (arg dict format)
- Plugin loading mechanism changes (ABC base class renamed/refactored)
- Tool schema format changes (OpenAI tool_call format evolution)

### MCP Tool Registration Flow (Stable)

```
MCP Server starts (stdio subprocess or HTTP)
    ↓ advertises tools via JSON-RPC 2.0 `tools/list`
Hermes Gateway connects via MCP client
    ↓ auto-discovers schemas
McpMcpClient → self.tools appended with mcp_ prefix
    ↓ LLM calls mcp_viking_search → MCP server handles it
```

**Survives Hermes upgrades** because:
- JSON-RPC 2.0 is a mature, unchanging spec (2013)
- MCP protocol is an external standard, not a Hermes-internal ABC
- Schema auto-discovery means no registration code changes
- Hermes's MCP client (`tools/mcp_tool.py`) is separated from the agent loop

### Lifecycle Hooks (Must Stay in Plugin)

MCP protocol covers tool calls only, not agent lifecycle:

| Hook | Purpose | MCP Replaceable? |
|------|---------|------------------|
| `initialize()` | Set up client, auth session | ❌ |
| `on_session_end()` | Flush to external store | ❌ |
| `system_prompt_block()` | Inject memory instructions | ❌ |
| `prefetch()` | Background context loading | ❌ |
| `shutdown()` | Clean threads, connections | ❌ |

These must remain in the Plugin. But the Plugin should be a **thin adapter** (~50 lines) calling REST API, not containing business logic or tool definitions.

### Optimal Decoupling Architecture

```
┌─ Hermes Agent ──────────────────────────────────────┐
│                                                      │
│  v1.0→v1.1→v1.2→v2.0  (Hermes upgrades)             │
│  ─────────────────────                               │
│  │ MCP Tools Layer │  ← SURVIVES upgrade unchanged   │
│  │ Thin Plugin (50L)│  ← Easy to adapt (~15 min)     │
│  └───────┬─────────┘                                 │
└──────────┼───────────────────────────────────────────┘
           │ REST API
┌──────────┼───────────────────────────────────────────┐
│  ┌───────┴──────────────────────────────┐            │
│  │  Memory Service (Docker, v-agnostic) │            │
│  │  OpenViking / TDB-AM / Custom        │            │
│  └──────────────────────────────────────┘            │
└──────────────────────────────────────────────────────┘
```

**Rules:**
1. Tools (`viking_search`, `viking_read`, `memory_recall`, etc.) → **MCP Server** (protocol-stable)
2. Lifecycle hooks (`on_session_end`, `prefetch`) → **Plugin thin adapter** (~50 lines, calls REST)
3. Business logic (search indexing, embedding, consolidation) → **Memory Service side** (Docker container)
4. Adding new memory features (agentmemory, etc.) → **New MCP Server**, zero Plugin changes

### Upgrade Protection Matrix

| Upgrade Scenario | Plugin-Only Design | **MCP-Decoupled Design** |
|-----------------|-------------------|--------------------------|
| Hermes changes MemoryProvider ABC | ❌ 6+ tools + 500+ lines break | ✅ Only ~50 line Plugin affected |
| Hermes changes tool schema format | ❌ Tool reg fails | ✅ Schema auto-discovered from MCP |
| Hermes deprecates MemoryProvider ABC | ❌ Entire memory system dead | ✅ Tools via MCP still work |
| Memory Service upgrades REST API | ⚠️ Fix calls in Plugin | ✅ Same fix in MCP Server |
| Add new memory feature (e.g., agentmemory) | ❌ New Plugin needed | ✅ Add MCP Server, zero Plugin |

### Diagnostic: Verify Current Coupling

```bash
# Check which tools come from MemoryProvider (not MCP)
grep -n "memory_manager\.has_tool\|memory_manager\.handle_tool_call" run_agent.py

# List all MCP servers
hermes mcp list

# Check config for memory provider
grep -A5 "^memory:" ~/.hermes/config.yaml
```

## Related Skills

- `hermes-agent` — End-user CLI usage guide
- `hermes-diagnostics` — state.db queries and health reports
- `native-mcp` — MCP protocol deep-dive configuration
- `mcp-debugging` — MCP server debugging
- `skills-evolution-from-research` — Skill evolution framework
- `claude-managed-agents-research` — CMA architecture research, comparison with Hermes v2, self-evolution directions (ToolResult standardization, SessionEventLog, wake/replay)
- `launchd-service-management` — Creating launchd plists for Gateway persistence
- `hermes-evolver-integration` — Hermes + Evolver bridge for self-evolution
