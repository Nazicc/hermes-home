---
name: codebase-inspection
description: "Inspect and analyze codebases — LOC counting with pygount, language composition, code-vs-comment ratios, and systematic strategies for exploring repository structure via GitHub raw content or local files. Use when asked to check lines of code, repo size, language breakdown, or to deeply understand a repository's architecture. NOT for: analyzing GitHub repos to understand architecture (use github-deep-research instead), deep architectural inspection of Rust monorepos (use rust-monorepo-deep-dive), or understanding tool implementation patterns — those require reading source files directly, not LOC counting."
tags: [code-analysis, repository, pygount, loc, github-exploration]
related_skills: [github-deep-research, rust-monorepo-deep-dive, systematic-debugging, github-code-exploration]
---

## Purpose

Codebase inspection helps you rapidly understand an unfamiliar repository — its size, language composition, architecture patterns, and entry points — without spending hours reading through files. The key insight is that most codebases follow recognizable patterns (CLI+daemon, monorepo with workspaces, framework with hooks) that you can identify in minutes by looking at the right files first. This skill combines quantitative analysis (LOC stats via pygount) with qualitative exploration (reading key files via GitHub raw content) to give you a complete picture fast.

## Teaching: Why This Works

### LOC Counting vs Architectural Understanding

Two complementary approaches work together:

**Quantitative (pygount):** Gives you the big picture fast — which languages dominate, how much of the code is comments/docs vs logic, and which directories contain the most code. A single `pygount --format=summary` command answers "is this project Python-heavy or Rust-heavy?" in under 5 seconds.

**Qualitative (raw file exploration):** Answers "how does this code work?" without cloning. By reading files in priority order (README → manifest → entry point → core modules), you can infer the architecture faster than any automated tool.

### The Priority File Method

The core heuristic: **not all files are equally informative.** A project's `README.md` and dependency manifest usually tell you more in 2 minutes than reading 20 source files. The entry point (`main.rs`, `cli.py`, `index.ts`) reveals the module structure. Core modules reveal the design patterns. This skill encodes a proven file-reading priority order for multiple language ecosystems.

### GitHub Raw Content Over Cloning

Cloning a large repo can take minutes and consume significant disk space. GitHub's raw content API (`raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}`) lets you read any file in any public repo with a single HTTP GET — no clone needed. This means you can analyze 10+ repos in the time it takes to clone one.

## Examples

### Example 1: Rapid Assessment of a New Python Project

**Scenario:** Someone shares a GitHub URL to "check out this starter template" and wants to know if it's worth adopting.

**Approach:**
1. Fetch `README.md` via raw content API → identifies it as a FastAPI project with SQLAlchemy
2. Fetch `pyproject.toml` → sees dependencies: `fastapi`, `sqlalchemy`, `alembic`, `pydantic`
3. Fetch `src/app/main.py` (entry point) → sees router registration pattern, middleware stack
4. Run `pygount --format=summary --exclude='**/SKILL.md' src/` → 3,240 lines, 68% Python, 22% tests

**Outcome:** In under 3 minutes, determined the project is a standard FastAPI monolith with Alembic migrations — well-structured, easy to contribute to. No clone needed.

### Example 2: Debugging a Monorepo with Bloated Build Times

**Scenario:** A developer says "our monorepo build takes 15 minutes," suspecting a dependency issue.

**Approach:**
1. `pygount --format=csv --outfile=/tmp/loc.csv .` → detected 128,000+ lines in a Rust workspace with 42 crates
2. `pygount --format=summary --pattern='*.rs' src/` → src/ has 89,000 lines; crates/ has 39,000 lines
3. Explored `Cargo.toml` → workspace has 42 members, but `crates/legacy-ffi/` alone is 18,000 lines (C bindings)
4. Identified that `legacy-ffi` changes rarely but is compiled every time due to workspace-level build

**Outcome:** Isolated the root cause — the legacy FFI crate had no `[patch]` or conditional compilation guard. Created a build profile that cached `legacy-ffi` as a prebuilt artifact.

### Example 3: Evaluating an Unknown TypeScript Library Before Integration

**Scenario:** Need to decide whether to adopt a new npm package by understanding its internal architecture.

**Approach:**
1. Fetch `package.json` → peer dependencies on React 18+ and `zustand`
2. Fetch `src/index.ts` → exports a `createStore()` factory function
3. Fetch `src/createStore.ts` → sees provider pattern with context + reducer
4. `pygount --format=summary src/` → 4,200 lines total, 92% TypeScript

**Outcome:** Determined the library uses a lightweight state management approach familiar to the team — worth adopting. Passed on another library where `pygount` revealed 15,000 lines of polyfill code for IE11 compatibility.

## Common Anti-Patterns

### 🔴 Counting Everything Blindly
Running `pygount .` on a repo without excluding generated files, vendored dependencies, or SKILL.md files gives misleading results. A `node_modules/` directory can inflate line counts by 10-100x. A project with 5,000 lines of actual code might appear to have 500,000 lines.

**Fix:** Always use `--exclude='**/node_modules/**' --exclude='**/.git/**' --exclude='**/SKILL.md'`. For pygount specifically, use `--exclude` with glob patterns to filter out non-source directories before running.

### 🔴 Cloning Instead of Reading Raw Content
Defaulting to `git clone` for analysis wastes time and disk space. A 1MB clone of a monorepo with git history can be 200MB+. For most analysis tasks, raw content API access is faster and sufficient.

**Fix:** Always try the raw content API first. Only clone when you need git history (`git log`, `git blame`) or to run local tooling.

### 🔴 Assuming pygount Language Detection Is Perfect
pygount detects languages by file extension, which can be wrong for:
- `.h` files — detected as C, but could be C++ headers
- `.js` files — detected as JavaScript, but could be JSX-heavy React
- Custom extensions (`.gql`, `.tpl`, `.tf`) — may not be recognized at all

**Fix:** Verify the breakdown by running `pygount --format=summary --pattern='*.py' .` for each language you care about. Compare the sums to the total.

### 🔴 Skipping the README
It's tempting to jump straight to code ("show me the source"), but a README is the single most cost-effective file you can read. It tells you the project's purpose, architecture overview, and how to run it — information that could take 30+ minutes to reverse-engineer from source.

**Fix:** Always fetch and read the README first. Even a bad README tells you something (e.g., lack of documentation is itself useful data about project maturity).

## When NOT to Use This Skill

- **For deep architectural understanding of Rust monorepos** — use `rust-monorepo-deep-dive` instead, which handles workspace member resolution, daemon process topology, and IPC protocol analysis
- **For analyzing GitHub repos to extract plugin manifests or skill architectures** — use `github-deep-research` instead, which recursively walks repository trees
- **For understanding tool implementation patterns** — this skill gives you LOC stats and basic architecture, but tool call chains and MCP server patterns require reading source files directly. Use `systematic-debugging` or dedicated reading instead
- **For repos with >1000 files and deep git history** — consider `github-deep-research` instead, which handles large repo analysis more efficiently
- **For real-time performance analysis or profiling** — LOC counting doesn't measure runtime behavior; use dedicated profiling tools instead
- **For security audits of individual files** — use `git-secret-audit` or dedicated code review instead

## Cross-References

- [github-deep-research](/skills/web-research/github-deep-research/SKILL.md) — Deep research on GitHub repos, for large-scale repository analysis
- [rust-monorepo-deep-dive](/skills/optional-skills/rust-monorepo-deep-dive/SKILL.md) — Specialized Rust monorepo architecture analysis
- [github-code-exploration](/skills/optional-skills/github-code-exploration/SKILL.md) — Explore public GitHub repo source code structure
- [systematic-debugging](/skills/software-development/systematic-debugging/SKILL.md) — General debugging methodology for code issues
- [github-repo-exploration](/skills/optional-skills/github-repo-exploration/SKILL.md) — Efficient GitHub repo structure exploration via API
- [code-simplification](/skills/optional-skills/code-simplification/SKILL.md) — For refactoring and simplifying code after inspection
