---
name: hermes-agent-diagnostics
description: "Use when diagnosing Hermes Agent runtime issues — plugin import failures, MCP client connectivity, missing CLI prerequisites, skill compatibility testing, and environment verification. NOT for: routine health checks (use hermes-agent-daily-maintenance), SkillClaw routing issues (use skillclaw-hermes-proxy), or scheduled cron maintenance."
category: skills
---

# Hermes Agent Diagnostics

Diagnostic skill for Hermes Agent runtime environment. Run these checks when diagnosing skill failures, plugin errors, or MCP connectivity issues.

## Plugin Import Testing

Test each plugin in `~/.hermes/hermes-agent/plugins/`:

bash
python3 -c "import sys; sys.path.insert(0, '~/.hermes/hermes-agent/plugins'); import <plugin_name>; print('OK')"


Known plugins:
- `holographic` → memory system
- `context_engine` → context management
- `example_dashboard` → NOTE: known to fail with ModuleNotFoundError in some environments

## MCP Client Connectivity

Test MCP server connections:

python
from <mcp_package> import <client>
client = <client>()
client.ping()  # or equivalent health check


Known MCP clients:
- SimpleMem MCP server (sirchmunk) → test with `search_memories` call; connection closed errors indicate server not running

## CLI Tool Availability

Check required CLI tools for skill prerequisites:

bash
which <tool> 2>/dev/null || echo "NOT_FOUND"


Known CLI requirements:
- `gh` → GitHub CLI (github skills fallback to git+curl if absent)
- `memo` → Apple Notes (apple-notes skill)
- `remindctl` → Apple Reminders (apple-reminders skill)
- `imsg` → iMessage (imessage skill)

## Python Module Availability

Check required Python packages:

bash
python3 -c "import <module>" 2>&1


Known module requirements:
- `huggingface_hub` → huggingface-hub skill
- `mcp` → MCP integration
- `fastmcp` → fastmcp skill

## Skill Compatibility Testing

For skills at version 1.x, verify the skill body contains RIA-TV++ sections (R/I/A1/A2/E/B) or at minimum trigger/anti_trigger fields. Skills with only frontmatter and no body content are stubs that need enrichment.

bash
# Count lines in SKILL.md body after frontmatter
awk '/^---$/ && !done { done=1; next } { body++ } END { print body }' ~/.hermes/skills/<category>/<skill>/SKILL.md


## Version Compliance

Verify skill versions match expected format. Target: v2.0.0 with trigger/anti_trigger/quality_redlines frontmatter fields.

python
import re
from pathlib import Path

skills_dir = Path.home() / ".hermes" / "skills"
for skill_md in skills_dir.glob("*/*/SKILL.md"):
    content = skill_md.read_text()
    version = re.search(r'^version:\s*([\d.]+)', content, re.MULTILINE)
    has_trigger = 'trigger:' in content
    has_anti_trigger = 'anti_trigger:' in content
    # Report skills below v2.0.0 or missing trigger fields


