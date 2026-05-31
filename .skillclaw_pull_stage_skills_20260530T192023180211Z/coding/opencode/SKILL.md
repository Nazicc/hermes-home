---
name: opencode
description: "Delegate coding tasks to OpenCode CLI agent for feature implementation, refactoring, PR review, and long-running autonomous sessions. Requires opencode CLI installed and authenticated. NOTE: OpenAI Codex (codex CLI) is NOT installed on this machine — use this skill instead. For DeepCode (deepcode-hku) research engine with its own FastAPI backend, use the deepcode-research-engine skill instead."
category: coding
---

## Prerequisites

- **opencode CLI**: Installed at `/opt/homebrew/bin/opencode` (macOS) — verify with `which opencode`.
- **Authentication**: Run `opencode auth` or set `OPENAI_API_KEY` / `OPENAI_BASE_URL` environment variables before use.
- **Git repository**: The target project must be a git repository (`git init` if needed).
- **NOT for**: One-liner edits, small text changes, or tasks requiring tight iteration loops — use direct terminal commands instead.

## When to Use

Use `opencode` when:
- Implementing a new feature from a spec or description
- Large-scale refactoring across multiple files
- PR code review with context from a diff
- Batch fixing of issues from a list
- Long-running autonomous coding sessions where you hand off and monitor

## How to Use

bash
cd /path/to/project
opencode "<task description>"

# With specific model
opencode --model <model> "<task>"

# Long-running autonomous session
opencode --interactive "<task>"


### Example: Feature Implementation

bash
cd /path/to/project
opencode "Implement user authentication using JWT tokens with refresh token rotation"


### Example: Refactoring

bash
cd /path/to/project
opencode "Refactor the data layer to use repository pattern, extract interfaces, and add unit tests"


### Example: PR Review

bash
cd /path/to/project
git fetch origin
opencode "Review the changes in origin/main..HEAD for security issues and code quality"


### Example: Batch Issue Fixing

bash
cd /path/to/project
opencode "Fix all TODO comments in src/, replace deprecated numpy APIs, and add error handling"


## Integration with DeepCode (Research Engine)

For research-paper-to-code workflows, `deepcode-hku` (DeepTutor/DeepCode research engine) is installed separately as a pip package at `/Users/can/DeepCode`. It is a **different tool** from `opencode`:

- `opencode` → coding agent for implementation/refactoring
- `deepcode-hku` → research engine for transforming papers into working code

Do not confuse the two. If the task involves understanding a research paper and generating code from it, consider invoking `deepcode.py` from the DeepCode package instead.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `command not found: opencode` | CLI not in PATH | Check `which opencode`; install via `pip install opencode` or `brew install opencode` |
| `Authentication failed` | Missing or invalid API key | Run `opencode auth` or set `OPENAI_API_KEY` env var |
| `Not a git repository` | opencode requires git | `git init` in the project directory |
| Agent makes no progress | Ambiguous task description | Provide more specific, scoped instructions |

## Relationship to Other Skills

- **`codex`**: OpenAI Codex CLI — NOT installed on this machine. The `codex` skill redirects here. Use `opencode` instead.
- **`claude-code`**: Anthropic's Claude Code CLI — available as a separate skill. Use when Anthropic models are preferred or when working within Claude's ecosystem.
