---
name: launchd-user-agent
description: "Create and manage user-level launchd plists for background services on macOS. Use when setting up any background agent, MCP server, or long-running service to survive reboots via launchd (gui/$(id -u)/<Label>). NOT for system-wide services (requires /Library/LaunchDaemons + root), NOT for services managed by Homebrew (use brew services instead), NOT for one-off scripts (use cron instead)."
category: general
---

## Overview

macOS launchd is the standard way to run persistent background services that survive reboots. User-level agents run under your login session, start at GUI login, and survive logout/reboot.

- **Source** (git-tracked): `~/.hermes/hermes-agent/LaunchAgents/` or `~/.hermes/hermes-agent/launchd/`
- **Installed** (loaded by launchd): `~/Library/LaunchAgents/`
- **Label convention**: reverse-domain (e.g., `com.hermes.deerflow-mcp`)
- **User domain**: `gui/$(id -u)/`

## Plist Template

xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hermes.SERVICE-NAME</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd /path/to/service && command-to-start</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/path/to/service</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <key>KeepAlive</key>
    <dict/>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/tmp/com.hermes.SERVICE-NAME.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/com.hermes.SERVICE-NAME.stderr.log</string>
</dict>
</plist>


## Critical: Shell Flags

**Use `-c` (NOT `-lc`)** in ProgramArguments. The `-lc` flag causes launchd to fork a login shell, which is unreliable in the launchd environment and often results in silent failures.

Also ensure your `$PATH` is set correctly via `EnvironmentVariables` since launchd runs with a minimal environment. For additional profile sourcing or virtualenv activation, include it in the command string:

bash
source /etc/profile 2>/dev/null; source ~/.bash_profile 2>/dev/null; cd /path/to/service && exec command


For virtualenvs:

bash
source /path/to/venv/bin/activate && cd /path/to/service && exec python3 server.py


## Lifecycle Commands

| Action | Command |
|--------|---------|
| Load | `launchctl load ~/Library/LaunchAgents/PLIST.plist` |
| Unload | `launchctl unload ~/Library/LaunchAgents/PLIST.plist` |
| Restart | `launchctl unload ... && launchctl load ...` |
| Enable (allows running) | `launchctl enable gui/$(id -u)/LABEL` |
| Disable (prevents running) | `launchctl disable gui/$(id -u)/LABEL` |
| Check status | `launchctl print gui/$(id -u)/LABEL` |
| List all user agents | `launchctl list` |
| Remove permanently | `launchctl bootout gui/$(id -u)/LABEL` |

## Workflow

### 1. Create the plist

Write to `~/.hermes/hermes-agent/LaunchAgents/com.hermes.SERVICE.plist`.

### 2. Install

**Option A: Symlink** (recommended for git-tracked)
bash
mkdir -p ~/Library/LaunchAgents
ln -sf ~/.hermes/hermes-agent/LaunchAgents/com.hermes.SERVICE.plist \
  ~/Library/LaunchAgents/com.hermes.SERVICE.plist


**Option B: Copy** (one-time)
bash
cp ~/path/to/com.hermes.service.plist ~/Library/LaunchAgents/
chmod 644 ~/Library/LaunchAgents/com.hermes.service.plist


### 3. Load the service (two-step for user-level agents)

bash
# Step 1: Enable (required for GUI agents to survive logout/reboot)
launchctl enable gui/$(id -u)/com.hermes.SERVICE

# Step 2: Load (starts the service now)
launchctl load ~/Library/LaunchAgents/com.hermes.SERVICE.plist


> **NOTE**: `launchctl bootstrap` does NOT work reliably for user-level agents. Always use `enable` + `load`.

### 4. Verify

bash
# Check if running:
launchctl print gui/$(id -u)/com.hermes.SERVICE
launchctl list | grep com.hermes.SERVICE

# Or check the process:
ps aux | grep SERVICE-PROC-NAME

# Check logs:
cat /tmp/com.hermes.SERVICE.stderr.log
cat /tmp/com.hermes.SERVICE.stdout.log

# Check port binding (for server services)
lsof -i :ACTUAL_PORT


### 5. Test persistence

bash
# Restart the service after config changes:
launchctl unload ~/Library/LaunchAgents/com.hermes.SERVICE.plist
launchctl load ~/Library/LaunchAgents/com.hermes.SERVICE.plist

# Simulate logout/reboot behavior:
launchctl kickstart -kp gui/$(id -u)/com.hermes.SERVICE


## Common Patterns

### MCP Server (Python/Node)

xml
<key>ProgramArguments</key>
<array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>cd /path/to/mcp-server && exec python3 server.py</string>
</array>
<key>WorkingDirectory</key>
<string>/path/to/mcp-server</string>


For Python virtualenvs, ensure the venv's Python is in PATH or use the absolute path:

xml
<string>/path/to/venv/bin/python /path/to/mcp-server/server.py</string>


Or activate the venv in the command:

bash
source /path/to/venv/bin/activate && exec python3 server.py


### Node.js Server

xml
<key>ProgramArguments</key>
<array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>cd /path/to/node-server && exec node server.js</string>
</array>
<key>WorkingDirectory</key>
<string>/path/to/node-server</string>


### Vite/Frontend Dev Server

xml
<key>ProgramArguments</key>
<array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>cd /path/to/frontend && exec npm run dev</string>
</array>
<key>WorkingDirectory</key>
<string>/path/to/frontend</string>


**Note**: Vite auto-ports to the next available port if the default port (e.g., 5173) is already in use. Check the stdout log for the actual port assigned.

## Troubleshooting

### Service not starting

bash
# 1. Check if loaded
launchctl list | grep com.hermes.SERVICE

# 2. Check errors
cat /tmp/com.hermes.SERVICE.stderr.log

# 3. Check if enable is needed (common oversight)
launchctl enable gui/$(id -u)/com.hermes.SERVICE

# 4. Check the process manually (run what launchd would run):
/bin/bash -c "source /etc/profile 2>/dev/null; source ~/.bash_profile 2>/dev/null; cd WORKING-DIR && exec COMMAND ARGS"
# If this works but launchd fails → the plist is wrong

# 5. Check for port conflicts
lsof -i :PORT


### `launchctl load` says "Already loaded"

bash
# Unload first, then reload
launchctl unload ~/Library/LaunchAgents/com.hermes.SERVICE.plist
launchctl load ~/Library/LaunchAgents/com.hermes.SERVICE.plist


### Service dies immediately

- Check stderr log for error messages
- Verify `$PATH` includes needed binaries (set via EnvironmentVariables)
- If using a virtualenv, use absolute path to venv's Python binary or activate in command
- Verify `KeepAlive` is not conflicting (some servers don't daemonize; launchd expects them to stay in foreground — for those, remove `KeepAlive` or set `RunAtLoad` only)

### `bash: command not found` in logs

The shell inside launchd has minimal PATH. Either:
1. Set `PATH` in `EnvironmentVariables`:
   xml
   <key>EnvironmentVariables</key>
   <dict>
       <key>PATH</key>
       <string>/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin</string>
   </dict>
   
2. Or include explicit sourcing in the command string:
   xml
   <string>source /etc/profile 2>/dev/null; source ~/.bash_profile 2>/dev/null; exec ...</string>
   

### Port conflicts

Old orphaned launchd processes can hold ports and bind them before new instances start. Use:
bash
lsof -i :PORT

Kill orphans with `launchctl bootout gui/$(id -u)/<OLD_LABEL>` or `pkill` by PID from `ps aux`.

### Permission denied errors

- Ensure the plist file is readable
- Ensure the service's working directory and log paths are writable by your user

## Git Management

Store plist source files in git for reproducibility:

bash
# Option A: store in LaunchAgents/ subdirectory
~/.hermes/hermes-agent/LaunchAgents/com.hermes.service.plist

# Option B: store in launchd/ subdirectory
~/.hermes/hermes-agent/launchd/com.hermes.service.plist

# Symlink to LaunchAgents
ln -sf /path/to/source/com.hermes.service.plist \
    ~/Library/LaunchAgents/com.hermes.service.plist

# Commit the plist source
cd ~/.hermes/hermes-agent
git add LaunchAgents/com.hermes.service.plist
git commit -m "feat: add launchd plist for SERVICE-NAME"


## Checklist

- [ ] Label uses reverse-domain and matches filename (e.g., `com.hermes.SERVICE.plist`)
- [ ] ProgramArguments uses `-c` (NOT `-lc`) with proper command
- [ ] WorkingDirectory set explicitly
- [ ] EnvironmentVariables includes PATH (or manual sourcing in command)
- [ ] `RunAtLoad` set for auto-start on login
- [ ] `KeepAlive` set for auto-restart on crash (use `<dict/>` for always restart)
- [ ] Log paths point to `/tmp/` or writable directory
- [ ] Plist installed in `~/Library/LaunchAgents/`
- [ ] `launchctl enable gui/$(id -u)/LABEL` called after loading
- [ ] Service verified running: `launchctl list | grep LABEL`
- [ ] Plist committed to git under `~/.hermes/hermes-agent/LaunchAgents/`
- [ ] For virtualenv: activate before running Python services
- [ ] For Vite frontends: check stdout log for actual port if default is in use
- [ ] Log directory exists before loading (create with `mkdir -p logs/`)
- [ ] After editing plist: `unload` → edit → `load`
