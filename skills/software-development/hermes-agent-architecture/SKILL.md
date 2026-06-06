---
name: hermes-agent-architecture
description: "Hermes Agent 项目架构 — cli.py、run_agent.py、HermesCLI、AIAgent 的关系，hermes mcp 子命令、MCP 服务器配置、Gateway/Dashboard 端口、state.db 内部诊断、以及如何正确添加新命令和 handlers。Use when modifying Hermes codebase, managing MCP server connections, debugging gateway startup, understanding the CLI-to-Agent relationship, or reading hermes internal state. NOT for: general agent usage (use hermes-agent skill), MCP server implementation details, writing agent prompts, or managing skills (those have their own skills)."
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

## Self-Evolution Architecture (Three-Layer System)

Hermes Agent has a three-layer self-evolution system that runs at different timescales:

```
Layer 1: Per-Turn Background Review  (agent/background_review.py, 597 lines)
Layer 2: Context Compression         (agent/conversation_compression.py, 755 lines)
Layer 3: Curator Skill Maintenance   (agent/curator.py, 1800 lines)
```

### Layer 1: Background Review

**Files:** `agent/background_review.py` + `run_agent.py:AIAgent._spawn_background_review`

After every turn, if trigger conditions are met, a daemon thread forks a fresh `AIAgent` to review the conversation and update memory/skills autonomously.

**Trigger conditions** (defined in `agent/conversation_loop.py:run_conversation`):
- **Memory review**: Every `_memory_nudge_interval` turns (default 10) — turn-based counter in `agent._turns_since_memory`
- **Skill review**: Every `_skill_nudge_interval` tool iterations (default 10) — iteration-based counter in `agent._iters_since_skill`
- Both require `final_response` and no interruption to fire

**Initialization** (`agent/agent_init.py` lines 1067-1069):
```python
agent._memory_nudge_interval = 10
agent._turns_since_memory = 0
agent._iters_since_skill = 0
```

**Fork inheritance strategy** (key optimization — ~26% cost reduction from prefix cache reuse, see issue #25322 / PR #17276):
- Inherits parent's live runtime (provider, model, base_url, api_key, credential_pool) — avoids re-resolving from env vars
- Inherits `_cached_system_prompt` verbatim → same Anthropic prefix cache key
- `skip_memory=True` prevents external memory provider side effects
- Re-binds `_memory_store`, `_memory_enabled`, `_user_profile_enabled` from parent
- Sets `suppress_status_output = True` to keep fork lifecycle messages silent

**Three review prompts** (`agent/background_review.py`):

| Prompt | Lines | Focus | When used |
|--------|-------|-------|-----------|
| `_MEMORY_REVIEW_PROMPT` | ~10 | User persona/preferences | `review_memory=True` only |
| `_SKILL_REVIEW_PROMPT` | ~115 | Skill updates, 4-tier priority | `review_skills=True` only |
| `_COMBINED_REVIEW_PROMPT` | ~83 | Both (condensed) | Both triggers fired |

**Skill review 4-tier update priority:**
1. Patch the currently-loaded skill (from `skill_view` or `/skill-name`)
2. Patch an existing umbrella skill (scan library via `skills_list`)
3. Add a support file under existing umbrella (`references/`, `templates/`, `scripts/`)
4. Create a new class-level umbrella (last resort — prefer extending existing)

**Protected content (DO NOT capture as skills):**
- Environment-dependent failures (missing binaries, path errors)
- Negative claims about tools ("X tool is broken")
- Session-specific transient errors that self-resolved
- One-off task narratives

**Safety:**
- Auto-denies dangerous commands via `_bg_review_auto_deny` callback
- Tool whitelist: only `memory` + `skill_manage` tools allowed (enforced per-thread via `set_thread_tool_whitelist`)
- All stdout/stderr redirected to `/dev/null`
- Finally block ensures memory provider shutdown + agent close + callback cleanup

**Call flow:**
```
conversation_loop.py:4670  →  agent._spawn_background_review()
                                  →  spawn_background_review_thread()
                                       →  _run_review_in_thread() [daemon]
                                            →  fork AIAgent + whitelist
                                            →  run_conversation(COMBINED_REVIEW_PROMPT)
                                            →  summarize_background_review_actions()
                                            →  print "💾 Self-improvement review: ..."
```

### Layer 2: Context Compression

**File:** `agent/conversation_compression.py` (755 lines)

When conversation exceeds model context window threshold, auxiliary model summarizes:
- Uses compression lock (`_compression_lock_holder`) with pid:tid:agent-instance:nonce
- Background review forks use same lock — ensures compression and review don't collide

### Layer 3: Curator (Skill Library Maintenance)

**File:** `agent/curator.py` (1800 lines)

Background maintenance orchestrator for agent-created skills:
- Runs when agent is idle and last curator run > `interval_hours` ago
- Called from `cli.py` and `gateway/run.py` via `maybe_run_curator(idle_for_seconds=..., on_summary=...)`

**Time parameters:**
```python
DEFAULT_INTERVAL_HOURS = 24 * 7    # 7 days between curator runs
DEFAULT_MIN_IDLE_HOURS = 2          # agent must be idle 2h before curator fires
DEFAULT_STALE_AFTER_DAYS = 30       # skill → stale after 30 days inactivity
DEFAULT_ARCHIVE_AFTER_DAYS = 90     # stale → archive after 90 days
```

**Key invariants:**
- Only touches agent-created skills (via `tools/skill_usage.is_agent_created`)
- Never deletes — only archives (archive is recoverable)
- Pinned skills bypass all auto-transitions
- Uses auxiliary client; never touches main session's prompt cache
- State persisted in `~/.hermes/skills/.curator_state`

### Known Gaps

- `self-improvement-loop.md` reference doc is referenced in `background_review.py` docstring but missing on disk
- No cross-session pattern mining — background review only evaluates current turn
- No curator ↔ background_review coordination (could modify same skill concurrently)
- No metrics tracking self-evolution effectiveness (improvement rate vs "nothing to save" frequency)
- No A/B testing for review prompt quality

### Separate: DSPy Evolver Pipeline (External)

Independent from the three internal layers, Hermes also runs an **external DSPy MIPROv2-based evolver** 
that optimizes skill content via prompt generation. This is NOT the curator — it modifies skill
files directly using LLM-generated improvements, then deploys via a gate check.

**Known failure mode: content collapse.** MIPROv2 can degenerate skill bodies to 7-13% of original
size when no content-preservation metric exists. Mitigation:
- Fidelity metric (Jaccard overlap + edit distance) at weight 0.15 in fitness composite
- Triple-gate deploy: improvement > 0 AND fidelity composite > 0.3 AND size ≥ 30% of baseline
- Minimum 60 training examples per skill; 20 MIPROv2 iterations

See `references/evolver-content-collapse-mitigation.md` for full root-cause analysis, configuration,
and verification procedure.

## Related Skills

- `hermes-agent` — End-user CLI usage guide
- `hermes-diagnostics` — state.db queries and health reports
- `native-mcp` — MCP protocol deep-dive configuration
- `mcp-debugging` — MCP server debugging
- `skills-evolution-from-research` — Skill evolution framework
- `launchd-service-management` — Creating launchd plists for Gateway persistence
- `hermes-evolver-integration` — Hermes + Evolver bridge for self-evolution

## Reference Documents

The skill stores reference documents in its `references/` directory:

| File | Content |
|------|---------|
| `references/self-evolution-architecture-deep-analysis.md` | Full deep analysis of the three-layer system: prompt details, fork inheritance strategy, safety mechanisms, CMA comparison, and identified gaps |
| `references/self-improvement-loop.md` | Design doc referenced by `agent/background_review.py` docstring — covers philosophy, implementation architecture, trigger conditions, and known future directions |
| `references/evolver-content-collapse-mitigation.md` | Root cause analysis and mitigation for DSPy MIPROv2 content collapse (7-13% body size degeneration), including fidelity metrics and triple-gate deploy |
