---
name: github-deep-research
description: "Deep research on external GitHub repositories — fetch raw content, extract skill files, analyze plugin manifests, and compile findings. Use when asked to analyze, study, or research a GitHub repo in depth (not just get a summary). NOT for: summarizing a repo in one sentence, or when the agent already has local file access to the repo."
category: web-research
---

Use Python's `urllib.request` (via the **terminal** tool) to fetch raw content from GitHub.

> **IMPORTANT**: Do NOT use `delegate_task` with `acp_command=claude` or similar subagent delegation for GitHub web research — subagents in this environment read local filesystem content rather than browsing URLs.

## Fetch Function

python
import urllib.request, json

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8")


## URL Patterns

| Goal | URL |
|------|-----|
| Raw file content | `https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}` |
| Directory listing (GitHub API) | `https://api.github.com/repos/{owner}/{repo}/contents/{path}` |
| README at root | `https://raw.githubusercontent.com/{owner}/{repo}/main/README.md` |

## Research Workflow

1. **Start in parallel**: Fetch the README and root directory listing simultaneously to get the high-level structure.
2. **Follow the structure**: Explore subdirectories by fetching their GitHub API listings (for directories) or raw content (for key files like `SKILL.md`, `plugin.json`, `README.md`).
3. **Read plugin manifests**: Check for `.claude-plugin/marketplace.json`, `.plugin/plugin.json`, or similar — these define skill installation formats.
4. **Parallel fetches**: When exploring multiple independent paths, use parallel tool calls to speed up. Group related files together.
5. **Prioritize by relevance**: For large repos, fetch top-level docs first, then dive into subdirectories.

## Handling Empty or Failed Results

**IMPORTANT**: `urllib.request.urlopen()` can silently return an empty string (`""`) or None with no exception when a fetch fails (network error, DNS failure, or rate limiting).

If a fetch returns empty or None:
1. Retry once with a longer timeout (up to 30s)
2. For GitHub API listings that fail, fall back to fetching the raw directory path via the default branch.
3. If rate-limited (403), wait briefly or use `raw.githubusercontent.com` URL directly instead of the API.
4. If retries continue to fail, report the failure to the user rather than proceeding with empty data.

## Raw URLs vs GitHub API

- **Raw URLs** (`raw.githubusercontent.com`): Return actual file content — use for `README.md`, `SKILL.md`, YAML configs, source code, etc.
- **GitHub API** (`api.github.com/repos/.../contents/`): Return JSON with `name`, `type` (file/dir), `sha`, `download_url` fields — use for exploring directory structures.
- **API listings do not include file content** — fetch `download_url` from each file entry to get the actual content.

## Compiling Findings

For each repo researched, provide:
1. **Purpose**: What the project does and its significance
2. **Structure**: Key directories, files, and their roles
3. **Key capabilities**: Main features, tools, or techniques demonstrated
4. **Installation/Setup**: How to run or deploy the project
5. **Notable patterns**: Reusable code patterns, architectural approaches, or interesting techniques
6. **Limitations or caveats**: Known issues, security warnings, deprecated components
