---
name: skillclaw-hermes-proxy
description: "SkillClaw proxy + Hermes Agent routing architecture — install, watchdog, reboot recovery. For Hermes Agent routing through SkillClaw (localhost:30000) to MiniMax API. NOT for: general YAML editing, non-Hermes launchd services, or skill security bypass."
category: infrastructure
---

## Architecture Overview


Hermes Agent (gateway)
    │  api_key: skillclaw, base_url: http://127.0.0.1:30000/v1
    ▼
SkillClaw Proxy (localhost:30000)
    │  reads key from ~/.skillclaw/shared/hermes-team/current_minimax_key
    │  (JSON format: {provider, key_id, label, api_key, strategy})
    ▼
MiniMax API (api.minimaxi.com)


## Hot-Reload Chain (Three Layers)

SkillClaw does NOT import Hermes credential_pool.py directly. Instead:

1. **Hermes exports** active key → `~/.skillclaw/shared/hermes-team/current_minimax_key` (JSON format)
2. **key_reloader daemon** (`skillclaw_key_reloader.py`) polls every 5s, sends SIGUSR1 when key changes
3. **SkillClaw** handles SIGUSR1 → reloads from JSON → continues routing

## Install SkillClaw

bash
npm install -g skillclaw
# or
pip install skillclaw

skillclaw --version


## Configure Hermes Agent

Edit `~/.hermes/config.yaml`:

yaml
provider: custom
custom_endpoint: http://localhost:30000
model: your-model-name


## Health Check Script

**Path:** `~/.hermes/skillclaw-health.sh`

**IMPORTANT**: Do NOT use `awk` to parse YAML for indent detection — the `model:` block and `default:` key have identical indentation (2 spaces), so awk's `indent >= 2` condition triggers on the very first line of the file and always exits early.

Correct approach: use Python to find the exact `[model_start, model_end)` line range of the `model:` block, then patch within that range only.

python
#!/usr/bin/env python3
import re, sys, yaml, os

CONFIG = os.path.expanduser("~/.hermes/config.yaml")

def patch_provider(provider="custom"):
    with open(CONFIG) as f:
        lines = f.readlines()

    # Find model: block line range precisely
    model_start = None
    model_end = None
    for i, line in enumerate(lines):
        if re.match(r'^model:\s*$', line):
            model_start = i
        elif model_start is not None and re.match(r'^\S', line) and not line.startswith('#'):
            # Found next top-level key (non-comment, non-blank, no indent)
            model_end = i
            break
    if model_end is None:
        model_end = len(lines)

    # Check current value
    for i in range(model_start, model_end):
        if lines[i].strip().startswith("provider:"):
            current = lines[i].split(":", 1)[1].strip()
            if current == provider:
                print(f"Already set: provider={provider}")
                return
            lines[i] = f"provider: {provider}\n"
            break

    with open(CONFIG, "w") as f:
        f.writelines(lines)
    print(f"Patched provider -> {provider}")

patch_provider("custom")


Make it executable:

bash
chmod +x ~/.hermes/skillclaw-health.sh


## Watchdog Separation (CRITICAL)

Do NOT put `KeepAlive` in the health check script plist. The health script is a one-shot remediation script — `KeepAlive` will cause launchd to re-run it immediately after it completes, creating an infinite loop.

**Two separate plists are required:**

### 1. Health check plist — periodic timer, no KeepAlive

`~/Library/LaunchAgents/com.hermes.skillclaw-health.plist`

xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hermes.skillclaw-health</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/can/.hermes/skillclaw-health.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/hermes-health.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/hermes-health.err</string>
</dict>
</plist>


### 2. Proxy watchdog plist — WITH KeepAlive

`~/Library/LaunchAgents/com.hermes.skillclaw-proxy.plist`

xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hermes.skillclaw-proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/can/.hermes/hermes-agent/start-skillclaw-proxy.sh</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/skillclaw-proxy.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/skillclaw-proxy.err</string>
</dict>
</plist>


## Gateway-Wrapper Startup Order (CRITICAL)

**SkillClaw proxy MUST start before Hermes gateway.** If Hermes starts first and SkillClaw isn't ready, Hermes will fail to route and may enter a crash loop.

If restarting after a crash: verify SkillClaw is up first, then restart Hermes.

## Load/Unload Commands

bash
# Load both agents
launchctl load ~/Library/LaunchAgents/com.hermes.skillclaw-health.plist
launchctl load ~/Library/LaunchAgents/com.hermes.skillclaw-proxy.plist

# Unload
launchctl unload ~/Library/LaunchAgents/com.hermes.skillclaw-health.plist
launchctl unload ~/Library/LaunchAgents/com.hermes.skillclaw-proxy.plist

# Verify
launchctl list | grep skillclaw
launchctl bslist | grep hermes


## Smoke Test

bash
# Check SkillClaw is running
curl -s http://localhost:30000/health

# Check logs
tail -f ~/.hermes/skillclaw-proxy.log ~/.hermes/skillclaw-proxy.err
tail -f /tmp/hermes-health.log /tmp/hermes-health.err


## Reboot Recovery

Both plists have `RunAtLoad: true`, so they start automatically after reboot.

## Critical Bug: Path Operator Precedence in key_reloader.py

**Symptom**: Reloader sends redundant SIGUSR1 on every poll cycle (visible in logs as consecutive reloads from 17:53:33 to 17:53:45).

**Root cause**: Python `Path` operator precedence bug:

python
# WRONG — `write_text` called on intermediate path
Path.home() / ".skillclaw" / ".last_loaded_key".write_text(key)
#               ^^^^^^^^^^^^^ Path object, write_text succeeds here
#                                              then / ".last_loaded_key" is orphaned

# CORRECT — build full path first
cache_path = Path.home() / ".skillclaw" / ".last_loaded_key"
cache_path.write_text(key)


The incorrect version writes the key to `Path.home() / ".skillclaw"` (a directory path) as if it were a file, silently succeeding. On the next poll, the cache file doesn't exist, so the reloader always sees a "change" and sends SIGUSR1 repeatedly.

**Fix**: Always build the full Path before calling `.write_text()`.

## Evolve Server

The evolve server (`ai.hermes.skillclaw-evolve`, running via launchd) processes sessions every 300s:
- Reads from `~/.skillclaw/records/conversations.jsonl` + `prm_scores.jsonl`
- Runs 3-stage pipeline: Summarize → Aggregate → Execute
- Publishes evolved skills directly to `~/.skillclaw/shared/hermes-team/skills/`
- Threshold: `push_min_effectiveness=0.3`

## Dead Launchd Service Cleanup Pattern

Check for stale/incorrect services:

bash
launchctl list | grep -i deerflow
ls ~/Library/LaunchAgents/ | grep -i deerflow


If a service plist references a non-existent repo (e.g., `deer-flow-repo` missing), the MCP server will fail silently. Remove the plist:

bash
launchctl unload ~/Library/LaunchAgents/com.hermes.deerflow-mcp.plist
rm ~/Library/LaunchAgents/com.hermes.deerflow-mcp.plist


## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Hermes says "connection refused" | SkillClaw not running | `launchctl start com.hermes.skillclaw-proxy` |
| Health script always restarts proxy | Model section patched incorrectly | Verify Python patch uses [model_start, model_end) range |
| Infinite respawn in logs | Health plist has KeepAlive=true | Remove KeepAlive, use StartInterval instead |
| Provider reverts to broken | Awk-based YAML parsing matched wrong section | Rewrite using Python with explicit range extraction |
| Proxy won't start | Port 30000 already in use | `lsof -i :30000` to check |
| Config not patched | Script missing execute permission | `chmod +x ~/.hermes/skillclaw-health.sh` |
| Reloader sends SIGUSR1 every poll | Path.write_text() called on intermediate Path | Build full path before calling .write_text() |

## Files Summary

| File | Purpose |
|------|---------|
| `~/.hermes/config.yaml` | Hermes Agent config pointing to localhost:30000 |
| `~/.hermes/skillclaw-health.sh` | Health check + auto-restore script |
| `~/Library/LaunchAgents/com.hermes.skillclaw-proxy.plist` | Persistent proxy watchdog (KeepAlive) |
| `~/Library/LaunchAgents/com.hermes.skillclaw-health.plist` | Periodic health timer (StartInterval=300) |
| `~/.skillclaw/shared/hermes-team/current_minimax_key` | Active key JSON (provider, key_id, api_key, strategy) |
| `~/.skillclaw/shared/hermes-team/` | Shared skills directory (SkillClaw pushes evolved skills here) |
| `~/.skillclaw/records/conversations.jsonl` | Session records for evolve server |
| `~/.skillclaw/records/prm_scores.jsonl` | PRM scores for evolve engine |
| `~/.skillclaw/logs/evolve-server.out.log` | Evolve server activity log |
| `~/.hermes/scripts/skillclaw_key_reloader.py` | Key reloader daemon script |
| `~/.hermes/agent/credential_pool.py` | Hermes credential pool (round_robin strategy) |

## NOT for

- General YAML editing (use a dedicated YAML skill)
- Non-Hermes launchd services (use launchd-service-manager)
- Skill security bypass (use hermes-agent-architecture)
