---
name: codex
description: "Use when delegating coding tasks to OpenAI Codex CLI — building features, refactoring, PR reviews, and batch issue fixing. NOT for: when codex CLI is not installed (use opencode instead), non-git repositories, or when opencode is preferred."
category: general
---

# Codex Skill

Delegate coding tasks to OpenAI Codex CLI agent for feature implementation, refactoring, PR reviews, and long-running autonomous sessions.

## Environment Status

| Component | Status |
|-----------|--------|
| Codex CLI (OpenAI) | ❌ Not installed — `which codex` → not found |
| OpenCode CLI | ✅ Installed v1.4.3 — use for autonomous coding on this machine |
| Git repository | Required — Codex uses git history for context |
| deepcode-hku | Separate pip package — research paper-to-code engine, NOT a codex replacement |

**Current environment**: OpenAI Codex CLI is not installed. Use the **`opencode`** skill instead for CLI-based autonomous coding tasks.

## Prerequisites

- OpenAI Codex CLI installed (`brew install openai-codex` or `npm install -g @openai/codex`)
- Codex CLI authenticated (`codex --auth`)
- Git repository (codex requires a git repo to track changes)
- OpenAI API key configured in environment

## Usage

### Feature Implementation

bash
# Start a new coding session
codex --prompt "Implement the user authentication feature"

# With specific context
codex --prompt "Add rate limiting to the API endpoints" --context "backend/api/v1/"


### Refactoring

bash
codex --prompt "Refactor the data layer to use the repository pattern" --context "src/models/"


### PR Reviews

bash
# Review a pull request
codex --review "https://github.com/owner/repo/pull/123"

# Or use the review command directly
codex --review


### Batch Issue Fixes

bash
# Process multiple issues from a GitHub project
codex --issues "--label=bug --state=open" --auto-commit

# Batch fix all instances of a pattern
codex --batch "fix all instances of pattern X"


### Model Selection

bash
# Specify a different model
codex --model claude "fix the login bug"


## Output

Codex will:
1. Analyze the codebase context
2. Make changes with git tracking
3. Create commits per logical change
4. Report summary of all changes made

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All tasks completed successfully |
| `1` | Partial completion (some tasks failed) |
| `2` | CLI error (not installed, not authenticated) |

## Distinction from Related Skills

| Skill | What it is | When to use |
|-------|------------|-------------|
| `codex` | OpenAI Codex CLI (NOT installed on this machine) | Only if Codex CLI is available in target environment |
| `opencode` | OpenCode CLI agent v1.4.3 (INSTALLED) | Primary choice for autonomous coding on this machine |
| `deepcode-hku` | DeepCode Research Engine (pip package) | Research paper to code workflows, not general coding delegation |

## Key Differences: Codex vs OpenCode

| Feature | Codex | OpenCode |
|---------|-------|----------|
| Provider | OpenAI | Various (SambaNova, etc.) |
| Context window | Limited | Extended (200K+ tokens) |
| Multi-file projects | Basic | Advanced |
| This machine | NOT INSTALLED | AVAILABLE |

## Important Notes

- **Requires git repository** — Codex uses git history for context
- **Requires OpenAI API key** configured in environment
- Use `--model` flag to specify model (e.g., `--model claude`)
- For research paper implementation, use `deepcode-hku` directly — it is an HKU research paper-to-code engine with its own FastAPI backend, NOT a codex replacement
- Since codex is not installed on this machine, this skill serves as documentation only

## Purpose

Delegate coding tasks to OpenAI Codex CLI for feature implementation, refactoring, PR review, and batch issue fixing, leveraging Codex's git-aware context gathering and autonomous commit workflow to reduce manual coding overhead.

## Why This Works

**Concept 1: Codex uses git history as context, so it understands the full project state without explicit file lists.** Unlike prompting a general LLM with selected file contents, Codex reads the git log, diff, and tree to understand what exists, what changed recently, and how the codebase is structured. This means the agent can make context-aware edits — renaming a function finds all callers, adding a field knows the existing schema, and a refactor understands the architecture.

**Concept 2: Batch and issue modes scale Codex from single-task assistant to multi-task autonomous worker.** The `--issues` flag processes an entire GitHub project's open bugs in one session, automatically loading each issue, making a fix, and committing. The `--batch` flag fixes every instance of a pattern across the codebase. These modes transform Codex from an interactive pair-programmer into an autonomous background worker that can process dozens of issues without supervision.

**Concept 3: The git-aware commit workflow gives you a clean, reviewable history.** Each logical change gets its own commit with a descriptive message. This means you can review changes per-task, roll back individual commits, and push a clean PR without "fixup" commits. The alternative (an LLM dumping all changes as a single diff) produces an opaque blob that's hard to review or revert.

## Examples

**Good: Implementing a new feature with Codex in an existing codebase.** Context: A team member asks you to add pagination to the `/api/users` endpoint. Instead of reading the codebase and making changes manually, delegate to Codex with context pointing at the API routes directory. Codex reads the git history for existing endpoint patterns, generates the pagination code matching the project's conventions, and creates a clean commit.

```bash
cd /path/to/project
codex --prompt "Add cursor-based pagination to /api/users endpoint with page_size param" \
  --context "backend/routes/api/"
# Codex: reads git log, understands FastAPI routing pattern,
#        implements pagination, creates commit "feat: add pagination to /api/users"
```

**Good: Batch-fixing a deprecated API call across the entire codebase.** Context: The `requests.get` library is being replaced with `httpx.AsyncClient` across a 200-file project. Use `--batch` to find and fix every instance in one session, with each file getting its own commit for reviewability.

```bash
codex --batch "replace all requests.get() calls with httpx.AsyncClient().get()"
# Codex: iterates every file, replaces each call, commits per file
# Exit 0: all replacements done
```

**Good: Reviewing a pull request before merging.** Context: A colleague opened PR #456 with a major refactor. Use `--review` to get an automated analysis of correctness, security, and style adherence. Codex reads the diff, checks for common issues, and returns a structured review.

```bash
codex --review "https://github.com/org/project/pull/456"
# Output: line-by-line comments with severity ratings
# (INFO, WARNING, ERROR) for each finding
```

**Good: Processing all open bugs tagged "priority:high" in a sprint.** Context: The project has 15 open high-priority bugs. Use `--issues` with label filtering to process them in one autonomous session. Codex loads each issue, reproduces the bug, applies a fix, and commits. Return at the end to review all changes.

```bash
codex --issues "--label=priority:high --state=open" --auto-commit
# Codex: processes 15 bugs one by one, commits per fix
# Exit 1 if some bugs couldn't be fixed (partial completion)
```

## Anti-Patterns

**Anti-Pattern 1: Running Codex outside a git repository.** Codex uses git history for context — `git log`, `git diff`, `git tree` are its primary data sources. Running it outside a repo produces an error or causes Codex to create a new repository, losing all project history. Always initialize git first.

**Anti-Pattern 2: Giving Codex open-ended prompts without context boundaries.** "Fix all the bugs" in a 50,000-file monorepo will overwhelm Codex's context, produce irrelevant changes, or time out. Always scope the prompt with either a file-path `--context` limit, a specific issue description, or both. Narrow prompts produce better, safer results.

**Anti-Pattern 3: Not reviewing Codex commits before pushing to shared branches.** Codex can introduce subtle bugs — wrong import path, off-by-one in a loop, missing error handling — that look right at a glance. The git-per-change commit model is designed for review. Always run `git diff HEAD~N --stat` and spot-check the changes before pushing.

**Anti-Pattern 4: Using Codex for codebase-aware prompts but switching to a non-OpenAI model via --model.** The `--model` flag routes to a different provider, but Codex's git-context gathering and commit workflow are still OpenAI-CLI features. The underlying model may not support the same tool-calling or context-window patterns. Test the model on a small task first.

## When NOT to Use

- When `opencode` is already installed and preferred (current machine has OpenCode v1.4.3, not Codex CLI) — use OpenCode for all autonomous coding on this machine.
- For non-git repositories — Codex requires git history for context gathering and diff generation. Use direct file editing or general prompt completion instead.
- For research-paper-to-code workflows — use `deepcode-hku` directly (its own FastAPI backend, pip package). Codex has no paper parsing capability.
- For single-line edits or simple find-and-replace across files — Codex's full startup cost (reading git log, model initialization) is disproportionate. Use grep/sed or the patch tool.
- For codebases with very large context requirements (>200K tokens of active code) — Codex's context window may be limiting. Prefer OpenCode which supports extended 200K+ token contexts.
- When the API key is not configured or rate limits are tight — Codex makes multiple LLM calls per session (one for planning, one per file change, one for commit messages). Each call counts against your API quota.

## Cross-References

- **opencode** — Primary autonomous coding skill for this machine (v1.4.3 installed). Use instead of codex when Codex CLI is unavailable, with extended 200K+ token context support.
- **deepcode-hku** — Research paper-to-code engine (separate pip package, FastAPI backend). Use for implementing code from academic papers, not for general coding delegation.
- **hermes-agent-architecture** — The underlying agent loop and tool-calling infrastructure. Understanding this helps scope Codex prompts to match what Codex can actually execute (tool calls, file edits, git operations).
- **code-quality** — Code review and quality enforcement. Codex commits should pass through the same review pipeline; this skill defines the quality gates.
- **hermes-agent-skill-standards** — General skill authoring conventions; coding-delegation skills are a specialization with mandatory installation status documentation, git requirement coverage, and cross-platform fallback guidance.
