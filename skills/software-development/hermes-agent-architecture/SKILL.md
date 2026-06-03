---
name: hermes-agent-architecture
description: "Hermes Agent 项目架构 — cli.py、run_agent.py、HermesCLI、AIAgent 的关系，hermes mcp 子命令、MCP 服务器配置、Gateway/Dashboard 端口、state.db 内部诊断、以及如何正确添加新命令和 handlers。Use when modifying Hermes codebase, managing MCP server connections, debugging gateway startup, understanding the CLI-to-Agent relationship, or reading hermes internal state. NOT for: general agent usage (use hermes-agent skill), MCP server implementation details, writing agent prompts, or managing skills (those have their own skills)."
category: general
---

## Purpose

Understanding Hermes Agent architecture prevents the most common development mistakes: placing MCP servers in wrong directories (they won't persist across git clones), creating independent launchd plists for MCP servers (they're subprocesses of the Gateway and get killed), or putting business logic directly in cli.py (it belongs in AIAgent/routes). This skill documents the actual codebase structure so you add features and fix bugs correctly the first time.

---

## Why This Works

### 1. Process Isolation Prevents Cascade Failures

The Gateway-to-MCP-servers process model is deliberately one-directional: Gateway spawns MCP servers as disposable stdio subprocesses, not the other way around. This means:

- A crashing MCP server never takes down the Gateway
- Gateway restarts automatically restart all MCP servers without user intervention
- Memory leaks in a long-running MCP server are contained to that subprocess

This is why launchd plists should only exist for the Gateway (and Sirchmunk) — everything else is a child process that gets cleaned up on Gateway restart.

### 2. Config-Driven Discovery Reduces Boilerplate

The `config.yaml` `mcp_servers` node and skills discovery path form a two-level registry system: config declares what exists, and the filesystem determines what's loaded. This means:

- Adding a new MCP server is one `hermes mcp add` command (writes one YAML block)
- Adding a new skill is one SKILL.md file (no registration needed)
- Removing either is a single operation

No database migrations, no import statements, no plugin registration hooks. The filesystem IS the registry.

### 3. state.db as Single Source of Truth

Session JSON files only contain message text. Token counts, end_reason, tool_call_count, compression_count — these live in state.db. When you need to answer "how many tokens did we use today" or "what's crashing," query state.db directly. This single-source design avoids the classic problem of splitting telemetry across files that can get out of sync.

---

## Anti-Patterns (Do NOT Do)

1. **Stashing MCP Servers Outside the Repo** — Placing MCP server code in `~/.hermes/skills/` or any path not under `~/.hermes/hermes-agent/mcp-servers/`. A repo clone or `git clean` destroys uncommitted code. Always commit MCP servers to the repo.

2. **Independent launchd Plists for MCP Servers** — Creating `~/Library/LaunchAgents/com.hermes.myserver.plist` for an MCP server that should be a Gateway child process. This leads to port conflicts, duplicate instances, and orphaned processes when Gateway restarts.

3. **Business Logic in cli.py** — Writing command handlers directly in `HermesCLI.build_parser()` or command functions. Business logic belongs in `AIAgent` or dedicated `agent/*_commands.py` modules. CLI is a thin presenter layer.

4. **Reading Session JSON for Metrics** — Parsing `~/.hermes/sessions/*.json` for token counts or end_reason. These files are message blobs. Use state.db SQLite queries instead — it has the actual metrics in indexed columns.

5. **Direct `sys.exit()` in Command Handlers** — Calling `sys.exit(1)` from a command handler kills the Gateway process. Use `raise click.Abort()` or return an error object instead.

---

## Examples

### Example 1: Adding a New MCP Server Correctly (Good)

**Context**: You built a new `gitanalyzer-mcp` package that wraps Git analysis tools.

**Correct approach**:
1. Place the code at `~/.hermes/hermes-agent/mcp-servers/gitanalyzer-mcp/`
2. Register with `hermes mcp add gitanalyzer --command python3 --args "-m mcp_servers.gitanalyzer_mcp"`
3. Verify: `hermes mcp list` shows `gitanalyzer | python3 -m … | ✓ enabled`
4. Commit: `cd ~/.hermes/hermes-agent && git add mcp-servers/gitanalyzer-mcp/ && git commit`

**Result**: A `git clone` on another machine pulls the server automatically. No manual plist file. No port conflicts.

**Why this works**: The code lives inside the Hermes repo (not a random `~/.hermes/skills/` dir), and the Gateway manages its lifecycle.

### Example 2: Wrong Directory, Lost MCP Server (Bad)

**Context**: You set up a Sirchmunk search MCP server.

**Mistake**: You placed the Sirchmunk adapter script at `~/.hermes/custom-servers/sirchmunk.py` and added it to `config.yaml` manually.

**What happened**: After running `hermes update` (which does `git pull` on the Hermes repo), the `git pull` succeeded but your `custom-servers/` directory outside the repo was untouched. However, your next `git clean -df` in the Hermes repo didn't delete it, so you thought it was safe — until you reinstalled Hermes on a new machine and forgot about `custom-servers/`.

**Why this failed**: Any code that lives outside the Hermes repo won't survive a fresh install or machine migration. The single rule is: *code that the agent needs goes in the Hermes repo*.

### Example 3: Launchd Plist for an MCP Subprocess (Bad)

**Context**: A developer set up a launchd plist for a MCP server thinking it needs to be persistent.

**Mistake**: Created `~/Library/LaunchAgents/com.hermes.deerflow-gateway.plist` for a DeerFlow MCP server.

**What happened**: The launchd plist started a second DeerFlow MCP process (port 8001) independently of the Gateway. When the Gateway also spawned its own DeerFlow MCP, two instances ran simultaneously, both trying to bind the same port. Gateway logs showed `EEXIST: Address already in use`.

**Why this failed**: MCP servers are children of the Gateway. When the Gateway starts, it spawns every configured MCP server. A separate launchd plist creates a duplicate. The correct fix is to remove the plist and let the Gateway manage the lifecycle.

---

## When NOT to Use

### Excluded by Domain

- **General Hermes usage** (config, chat, auth) → use `hermes-agent` skill
- **MCP server debugging** (crashes, timeouts) → use `mcp-debugging` skill
- **Evolver integration** (self-evolution, skill upgrades) → use `hermes-evolver-integration` skill
- **SimpleMem MCP setup** → use `simplemem-integration` skill
- **Skill evolution** (creating/modifying skills) → use `skills-evolution-from-research` skill

### Boundary Conditions

- **Don't use for writing agent prompts** — This skill documents the codebase, not prompting patterns
- **Don't use for user-facing troubleshooting** — If a user asks "why is Hermes slow," use `hermes-diagnostics` instead
- **Don't use for gateway deployment to new environments** — Use `hermes-atropos-environments` for deployment contexts
- **Don't use when you just need to list skills** — Use `hermes skills list` or the `skills_list` tool

---

## Project Structure Overview


hermes-agent/
├── cli.py                  # CLI entry point, HermesCLI class
├── run_agent.py            # Agent runtime core, AIAgent class
├── model_tools.py          # Tool orchestration — post_tool_call hook fires here (~L996)
├── toolsets.py             # Toolset definitions, _HERMES_CORE_TOOLS
├── hermes_state.py         # SessionDB — SQLite session store (FTS5)
├── gateway/                # Gateway server (HTTP API + MCP client)
│   ├── run.py              # Gateway HTTP server
│   ├── session.py          # SessionStore — conversation persistence
│   └── platforms/          # Adapters: telegram, discord, slack, whatsapp, ...
├── agent/
│   ├── conversation_loop.py  # Main agent loop — on_session_end, compression logic
│   ├── tool_executor.py      # Tool dispatch and execution isolation
│   ├── tool_dispatch_helpers.py # Tool result message formatting
│   ├── skill_commands.py     # /skill-name command routing
│   ├── prompt_builder.py     # System prompt assembly
│   ├── context_compressor.py # Auto context compaction
│   └── prompt_caching.py     # Anthropic prompt caching
├── hermes_cli/
│   └── plugins.py          # Plugin system — PluginContext, 15 hooks, register/invoke
├── tools/
│   ├── registry.py          # Central tool registry (schemas, handlers, dispatch)
│   ├── mcp_tool.py          # MCP client (~1050 lines)
│   └── ...                  # terminal_tool.py, file_tools.py, web_tools.py, etc.
├── plugins/                 # Installed plugins (disk-cleanup, observability/langfuse)
│   ├── disk-cleanup/
│   │   ├── plugin.yaml     # Plugin manifest (name, hooks, schedule)
│   │   └── __init__.py     # Pre/post tool call hooks
│   └── observability/
│       └── langfuse/
│           └── __init__.py
├── cron/
│   └── scheduler.py        # Scheduled task dispatcher
├── mcp-servers/            # MCP server implementations (git-tracked)
├── skills/                 # Built-in skills
├── tests/                  # Pytest suite
├── ui-tui/                 # Ink (React) terminal UI
├── tui_gateway/            # Python JSON-RPC backend for TUI
├── acp_adapter/            # ACP server for VS Code/Zed/JetBrains
└── environments/           # RL training environments (Atropos)


## Plugin System Architecture (hermes_cli/plugins.py)

The plugin system provides **15 lifecycle hooks** that plugins can register for. This is the runtime bridge between real agent execution and the self-evolution pipeline — **no plugin currently connects them**, which is the critical gap.

### Key Classes

- **`PluginContext`** (line 286) — per-plugin context: name, config, enabled/disabled, hook registrations
- **`PluginManager`** (line 1007) — singleton: discovers plugins from `plugins/` dirs, registers handlers, invokes hooks

### Available Hooks (15 total)

| Hook | Trigger Point | Current Registrants |
|------|---------------|---------------------|
| `on_startup` | Agent initialization | disk-cleanup (start periodic sweep) |
| `on_shutdown` | Agent shutdown | disk-cleanup (stop timer) |
| `pre_tool_call` | Before each tool invocation | disk-cleanup (check disk space) |
| `post_tool_call` | After each tool result received | evolution-recorder (captures runtime data for self-evolution) |
| `on_session_start` | New conversation begins | langfuse observability, evolution-recorder (initialize per-turn tracking) |
| `on_session_end` | Conversation finishes | langfuse observability, evolution-recorder (persist session summary to evolution.db) |
| `message_interceptor` | Between model response & rendering | langfuse |
| `on_error` | Unhandled exception | None |
| `config_updated` | Config file changes | None |
| `on_model_change` | Model switch | None |
| `on_tool_result` | Tool execution completed | None |
| `before_send` | Before message sent to platform | None |
| `after_send` | After message sent to platform | None |
| `on_compression` | Context compression triggered | None |
| `on_cron_tick` | Cron job tick | None |

### Hook Registration Pattern

```python
register_hook(plugin_name, hook_name, priority, handler_func)
# Priority: lower = runs first (100 = normal)
# Invocation: invoke_hook(name, *args, **kwargs) → sorted handlers called
```

### Where Hooks Fire (Hardcoded)

- **`post_tool_call`** — `model_tools.py:~L996`, inside `handle_function_call()`, right after tool returns
- **`on_session_end`** — `agent/conversation_loop.py`, session closure section (~L700+)
- **`pre_tool_call`** — `agent/tool_executor.py`, before tool dispatch
- **`message_interceptor`** — after model response, before user delivery

### Plugin Discovery

1. `~/.hermes/hermes-agent/plugins/` — repo-tracked first-party plugins  
2. `~/.hermes/plugins/` — user-installed plugins

Each plugin: `plugin.yaml` (manifest) + `__init__.py` (handlers)

### Self-Evolution 3-Layer Bridge (Implemented June 3, 2026)

```diff
Layer 1: Plugin System (runtime hook firing)
-    ↓ post_tool_call fires but NO plugin captures data
+    ↓ evolution-recorder captures tool data
Layer 2: SimpleMem Evolution (~/.hermes/simplemem_evolution/evolution.db)
-    ↓ 530 records exist, all synthetic — none from runtime capture
+    ↓ 531+ records — runtime captures being written via EvolutionStore
Layer 3: Evolution Pipeline (~/.hermes/hermes-agent-self-evolution/)
-    ↓ dataset_builder.py:BuildFromSessionDB() is a STUB
+    → dataset_builder.py:BuildFromSessionDB() is still a STUB
```

**Status (June 3, 2026):**
1. ✅ `evolution-recorder` plugin exists at `~/.hermes/hermes-agent/plugins/evolution-recorder/` — 3 files: `plugin.yaml`, `__init__.py`, `evolution_recorder.py`
2. ✅ Registers `post_tool_call`, `on_session_start`, `on_session_end` hooks
3. ✅ Writes tool executions and session summaries to `evolution.db` via `EvolutionStore.upsert()`
4. ✅ Config-enabled via `hermes plugins enable evolution-recorder` (requires `chflags nouchg` first on macOS with immutable flag)
5. ❌ `dataset_builder.py:BuildFromSessionDB()` is still a stub — evolution.db data cannot yet reach the GEPA optimizer
6. ❌ No bridge from evolution.db → evolution training pipeline (Layer 2 → Layer 3 gap)

**Design reference:** See `hermes-evolver-integration` skill for the full architecture mapping,
or `references/evolution-recorder-bridge.md` for implementation details and verification procedure.

### Config File Warning (macOS)

`~/.hermes/config.yaml` may have the `uchg` (user immutable) flag on macOS:
```bash
ls -lO ~/.hermes/config.yaml     # Check: 'uchg' in flags column
chflags nouchg ~/.hermes/config.yaml  # Remove flag to edit
# ... make changes (e.g. hermes plugins enable foo) ...
chflags uchg ~/.hermes/config.yaml    # Re-lock (optional)
```
This flag prevents `hermes plugins enable` and `hermes mcp add` from writing to config. Try those commands
first — if they fail silently, check and remove the flag.

---

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

---

## Cross-References

- **hermes-agent** — End-user CLI usage guide (complementary: this skill is for developers modifying Hermes)
- **hermes-diagnostics** — state.db queries and health reports for actual runtime telemetry
- **native-mcp** — MCP protocol deep-dive and configuration for adding HTTP MCP servers
- **mcp-debugging** — Debug MCP server crashes and timeouts during development
- **skills-evolution-from-research** — Skill evolution framework when adding new skills to the system
- **launchd-service-management** — Correct launchd plist creation for Gateway persistence
- **hermes-evolver-integration** — Hermes + Evolver bridge for self-evolution
- **systematic-debugging** — Debugging approach for runtime issues discovered via state.db
