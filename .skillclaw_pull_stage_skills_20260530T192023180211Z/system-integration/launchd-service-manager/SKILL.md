---
name: launchd-service-manager
description: "Create, debug, and manage macOS launchd plist services for hermes-agent infrastructure (MCP servers, backends, frontends). Use when: creating or managing launchd plist services, setting up MCP servers as persistent background services, troubleshooting launchd load/verify failures, or managing services that must survive reboots. NOT for: non-macOS systems, systemd/systemctl-based services on Linux, or one-off manual process invocations."
category: system-integration
---

# macOS Launchd Service Manager

Create and manage macOS launchd plist services for hermes-agent background services (MCP servers, backends, frontends) that must survive reboots.

## Workflow

### 1. Determine the Correct Label

Use a reverse-domain label:
- `com.hermes.deerflow-mcp`
- `com.hermes.deepcode-backend`
- `com.hermes.deepcode-frontend`

### 2. Choose User-Level vs System-Level

**Always use user-level (`gui/$(id -u)/`) for hermes-agent services.**

System-level (`/Library/LaunchDaemons/`) requires root and is for OS-level services.
User-level (`~/Library/LaunchAgents/`) runs under the logged-in user.

### 3. Create the Plist File

Plist location: `~/Library/LaunchAgents/com.hermes.<service-name>.plist`
Also commit to `~/.hermes/hermes-agent/LaunchAgents/` for git tracking.

**Template**:

xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hermes.<service-name></string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd /path/to/service && <start-command></string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/com.hermes.<service-name>.out.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/com.hermes.<service-name>.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>


**Critical**: Use `-c` (not `-lc`) in ProgramArguments. The `-lc` flag (login shell) is unreliable inside launchd — some macOS configurations treat it as invalid or silently ignore the command. Use `-c` with an explicit `cd` inside the command string instead.

### 4. Load the Service

bash
# Place the plist in ~/Library/LaunchAgents/ first
cp ~/.hermes/hermes-agent/LaunchAgents/com.hermes.<service-name>.plist ~/Library/LaunchAgents/

# For user-level plists, use enable first, then load
launchctl enable gui/$(id -u)/com.hermes.<service-name>
launchctl load ~/Library/LaunchAgents/com.hermes.<service-name>.plist


**Important**: `launchctl bootstrap` alone does NOT reliably start user-level GUI agents on modern macOS. The `launchctl enable` step is required before `launchctl load` for services with windows or GUI components.

### 5. Verify

bash
# Check if running
launchctl print gui/$(id -u)/ | grep com.hermes

# Check logs
tail -f /tmp/com.hermes.<service-name>.out.log
tail -f /tmp/com.hermes.<service-name>.err.log

# Check if the process is running
ps aux | grep <service-name>


### 6. Port Verification

If the service exposes a web interface, verify the correct port:

bash
# Check what's listening on expected ports
lsof -i :5173
lsof -i :5174
lsof -i :<expected-port>

# If Vite-based frontend is missing (shows nothing on expected port):
# It may have silently fallen back to the next available port.
# Vite auto-increments the port (e.g. 5173 → 5174) when the default is occupied.
# Find the actual port with:
lsof -i -P | grep <service-name>


### 7. Commit to Git

bash
cd ~/.hermes/hermes-agent
git add LaunchAgents/
git add mcp-servers/  # if MCP server code was moved to repo
git commit -m "feat: add launchd plists for <service-list>"
cd ~/.hermes/skills
git add launchd-service-manager/
git commit -m "docs: update launchd-service-manager"


## MCP Server Tracking

MCP server implementations that should survive hermes-agent upgrades should live under:


~/.hermes/hermes-agent/mcp-servers/


Not loose in `~/.hermes/` or `~/.config/`. This ensures git tracking and version control.

## Troubleshooting

### Service won't start

1. Check logs: `tail /tmp/com.hermes.<service-name>.err.log`
2. Verify plist is in `~/Library/LaunchAgents/`
3. Run the start command manually to check for errors
4. Verify `launchctl enable` was called (not just `bootstrap`)
5. Confirm bash `-c` (not `-lc`) is used in ProgramArguments

### Port already in use

Vite-based dev servers auto-migrate to next port (e.g., 5173 → 5174 → 5175).
Kill the orphaned process:

bash
# Find the process
lsof -i :<occupied-port>

# Kill it
kill <PID>


### Service starts but fails silently

Increase verbosity in the service's start command (add `--verbose` or `-v` flags) and check both stdout and stderr logs.

## Quick Reference: Complete Setup

bash
# 1. Create plist file
cat > ~/Library/LaunchAgents/com.hermes.<name>.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hermes.<name></string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd /path/to/service && <start-command></string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/com.hermes.<name>.out.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/com.hermes.<name>.err.log</string>
</dict>
</plist>
EOF

# 2. Load
launchctl enable gui/$(id -u)/com.hermes.<name>
launchctl load ~/Library/LaunchAgents/com.hermes.<name>.plist

# 3. Verify
launchctl print gui/$(id -u)/ | grep com.hermes.<name>
ps aux | grep <name>

# 4. Commit
cp ~/Library/LaunchAgents/com.hermes.<name>.plist ~/.hermes/hermes-agent/LaunchAgents/
cd ~/.hermes/hermes-agent && git add LaunchAgents/ && git commit -m "feat: add launchd plist for <name>"
