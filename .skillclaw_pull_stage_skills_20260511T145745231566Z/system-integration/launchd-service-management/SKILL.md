---
name: launchd-service-management
description: "Create, debug, and manage macOS launchd plist services for hermes-agent infrastructure (MCP servers, backends, frontends). Covers the full lifecycle: create plist → load → verify → troubleshoot → commit to git. NOT for system-wide LaunchDaemons (requires root), Linux systemd, or non-macOS platforms."
category: system-integration
---

## Overview

Create, debug, and manage user-level launchd plist services for hermes-agent infrastructure.

**When to use**: Creating or updating a background service (MCP server, backend, frontend) that must survive reboots, run as the current user, and start automatically on login.

**Constraint**: User-level services only (`~/Library/LaunchAgents/`). System-wide LaunchDaemons require root and are out of scope.

## Service Types

| Type | Location | Requires root |
|------|----------|---------------|
| User agent | `~/Library/LaunchAgents/` | No |
| System LaunchDaemon | `/Library/LaunchDaemons/` | Yes (out of scope) |

## Plist File Structure

Save to `~/Library/LaunchAgents/com.hermes.<service-name>.plist`.

**Critical fields:**

| Field | Value | Notes |
|-------|-------|-------|
| Label | `com.hermes.<name>` | Must match filename prefix (without `.plist`) |
| ProgramArguments | `[bash, -c, command]` | **Use `-c`, NOT `-lc`** — login interactive shell causes "operation not permitted" errors |
| RunAtLoad | `<true/>` | Start on system/user login boot |
| KeepAlive | `<true/>` or dict | Restart on crash; for Vite use `SuccessfulExit: false` |
| StandardOutPath | `/tmp/<name>.log` or `~/.hermes/logs/<name>.log` | Where to write stdout |
| StandardErrorPath | `/tmp/<name>.err` or `~/.hermes/logs/<name>.err` | Where to write stderr |
| ProcessType | `Interactive` | Required for GUI apps and user-level agents |

**Example — MCP server (stdio-based):**
xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hermes.deerflow-mcp</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>cd /Users/can/.hermes/hermes-agent/mcp-servers/deerflow && source .venv/bin/activate && python server.py</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/deerflow-mcp.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/deerflow-mcp.err</string>
  <key>ProcessType</key>
  <string>Interactive</string>
</dict>
</plist>


**Example — Backend (port listener):**
xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hermes.deepcode-backend</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>cd /Users/can/.hermes/hermes-agent/deepcode/backend && source .venv/bin/activate && uvicorn main:app --host 127.0.0.1 --port 8090</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/deepcode-backend.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/deepcode-backend.err</string>
  <key>ProcessType</key>
  <string>Interactive</string>
</dict>
</plist>


**Example — Frontend (Vite dev server):**
xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hermes.deepcode-frontend</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>cd /Users/can/.hermes/hermes-agent/deepcode/frontend && npm run dev</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>StandardOutPath</key>
  <string>/tmp/deepcode-frontend.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/deepcode-frontend.err</string>
  <key>ProcessType</key>
  <string>Interactive</string>
</dict>
</plist>


**Alternative PATH configuration** (if services can't find commands):
xml
<key>EnvironmentVariables</key>
<dict>
  <key>PATH</key>
  <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:~/.local/bin:$HOME/.local/bin</string>
</dict>


## Loading and Managing Services

bash
# Create log directory
mkdir -p ~/.hermes/logs ~/Library/Logs/hermes-agent

# Copy plist to LaunchAgents
cp ~/path/to/service.plist ~/Library/LaunchAgents/

# MUST enable first (enables the service for the user on login)
launchctl enable gui/$(id -u)/com.hermes.<service-name>

# Then load
launchctl load ~/Library/LaunchAgents/com.hermes.<service-name>.plist


> **Important:** Always run `enable` before `load` for user-level agents. Skipping `enable` causes the service to appear loaded but not actually start on reboot.

bash
# Unload (stops and removes from launchd, keeps plist file)
launchctl unload ~/Library/LaunchAgents/com.hermes.<service-name>.plist

# Unload AND disable (prevents auto-start on reboot)
launchctl disable gui/$(id -u)/com.hermes.<service-name>
launchctl unload ~/Library/LaunchAgents/com.hermes.<service-name>.plist

# Remove plist entirely
rm ~/Library/LaunchAgents/com.hermes.<service-name>.plist

# Force restart
launchctl kickstart -kp gui/$(id -u)/com.hermes.<service-name>
# Or: unload then load
launchctl unload ~/Library/LaunchAgents/com.hermes.<service-name>.plist
launchctl load ~/Library/LaunchAgents/com.hermes.<service-name>.plist


> **Note:** `launchctl bootstrap` does not work reliably for user-level agents on modern macOS. Use `launchctl load` directly.

## Port and Service Verification

bash
# Check if a port is listening
nc -z 127.0.0.1 <port> && echo "UP" || echo "DOWN"

# Check which process is on a port
lsof -i :<port>

# Check if running via launchctl
launchctl list | grep com.hermes.<service-name>

# Check detailed status
launchctl print gui/$(id -u)/ | grep com.hermes

# Check logs
cat ~/.hermes/logs/<service-name>.stderr.log
tail -f ~/.hermes/logs/<service-name>.stderr.log


**For MCP servers**, also verify the stdio interface is working:
bash
cd ~/.hermes/hermes-agent/mcp-servers/SERVER-NAME
npm start
# Expect: server starts on stdio, responds to JSON-RPC


## Troubleshooting

| Symptom | Check |
|---------|-------|
| Service not starting | `launchctl print gui/$(id -u)/...` for last exit status |
| TTY error (no job control) | Remove `-lc` from shell args; use `-c` instead |
| PATH issues | Set full `PATH` in `EnvironmentVariables` dict |
| Port already in use | `lsof -i :PORT` to find conflicting process |
| Label mismatch | Plist filename and `Label` key must match exactly |
| Service enabled but not running | `launchctl kickstart` to force start |

**Exit codes:**
- **Exit code 1**: Script/command failing — check stderr log, run manually
- **Exit code 126**: Permission denied — `chmod +x` the script

**Port Conflict Detection:**
If a service claims to be running but the port check shows a different process, or if Vite reports `localhost:PORT is in use` but shows a different port in the URL:

bash
# Find what's using the port
lsof -i :<expected-port>

# Check for orphaned launchd processes
launchctl print gui/$(id -u)/ | grep -A5 com.hermes

# Kill orphaned processes
launchctl bootout gui/$(id -u)/com.hermes.<service-name>
kill $(lsof -t -i :<port>)

# Reload
launchctl load ~/Library/LaunchAgents/com.hermes.<service-name>.plist


**Vite frontend note:** If the expected port (e.g., 3780) is occupied, Vite auto-rebinds to the next available port (e.g., 3782). Always check the actual URL in the output, not just the expected port.

**Service starts but immediately crashes (KeepAlive restarting):**
- The process exits within seconds
- Check for port conflict or startup race
- Use the wrapper script pattern below if another service must be ready first

## Service Startup Dependencies (Wrapper Script Pattern)

launchd user-level agents do NOT support `After=`/`Before=` ordering (unlike systemd). To enforce startup order (e.g., Service B must be running before Service A starts), use a **wrapper script**.

**Pattern: Port-check wrapper**

bash
#!/bin/bash
# gateway-wrapper.sh — ensures SkillClaw relay is up before gateway starts
set -e

if ! nc -z 127.0.0.1 30000 2>/dev/null; then
    echo "[$(date)] SkillClaw not running, starting..."
    launchctl start com.hermes.skillclaw
fi

# Wait for port to be ready (max 30s)
for i in $(seq 1 30); do
    if nc -z 127.0.0.1 30000 2>/dev/null; then
        echo "[$(date)] SkillClaw port 30000 ready"
        break
    fi
    sleep 1
done

# Now launch the dependent service
exec /full/path/to/actual-service-binary "$@"


Update the plist to use the wrapper:
xml
<key>ProgramArguments</key>
<array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>/Users/can/.hermes/gateway-wrapper.sh</string>
</array>
<key>KeepAlive</key>
<true/>


**Key design points:**
- Keep `KeepAlive: true` on the **wrapper**, not on the inner process
- Port detection (`nc -z`) is more reliable than process detection (`pgrep`)
- Always include a timeout (30s max) to prevent indefinite hangs
- Verify correct ordering by checking timestamps in the wrapper's stdout log

## Git Integration

Commit plist files to the hermes-agent git repo for reproducibility:

bash
# Store plists in the repo
mkdir -p ~/.hermes/hermes-agent/launchd
cp ~/Library/LaunchAgents/com.hermes.*.plist ~/.hermes/hermes-agent/launchd/

# Commit
cd ~/.hermes/hermes-agent
git add launchd/
git commit -m "feat: add launchd plists for <service names>"


**Restore workflow** (on fresh clone):
bash
for f in ~/.hermes/hermes-agent/launchd/*.plist; do
    label=$(basename "$f" .plist)
    cp "$f" ~/Library/LaunchAgents/
    launchctl enable gui/$(id -u)/"$label"
    launchctl load "$f"
done


## Quick Reference

| Command | Purpose |
|---------|---------|
| `launchctl load plist` | Start/load a user-level service |
| `launchctl unload plist` | Stop a user-level service |
| `launchctl enable gui/$(id -u)/LABEL` | Enable service for user (run before load) |
| `launchctl disable gui/$(id -u)/LABEL` | Disable service (prevents auto-start) |
| `launchctl list` | List all loaded services |
| `launchctl print gui/$(id -u)/LABEL` | Detailed status of a service |
| `launchctl kickstart -kp gui/$(id -u)/LABEL` | Force restart |
| `launchctl bootout gui/$(id -u)/LABEL` | Kill and remove |
| `launchctl error` | Last exit code explanation |
| `nc -z 127.0.0.1 <port>` | Check if port is listening |
| `lsof -i :<port>` | Find process on port |
| `kill $(lsof -t -i :<port>)` | Kill orphan on port |

## Checklist

- [ ] Write the shell script if needed (`~/.hermes/scripts/<service-name>.sh`)
- [ ] Make it executable: `chmod +x ~/.hermes/scripts/<service-name>.sh`
- [ ] Test manually: `bash ~/.hermes/scripts/<service-name>.sh`
- [ ] Plist file placed in `~/Library/LaunchAgents/`
- [ ] `ProgramArguments` uses `-c` not `-lc`
- [ ] `launchctl enable gui/$(id -u)/<label>` run before load
- [ ] `launchctl load` succeeds without error
- [ ] Port binding verified with `nc -z` or `lsof`
- [ ] Log files show service started successfully
- [ ] Plist committed to hermes-agent git repo
- [ ] Fresh-rebuild restore script tested or documented
