---
name: github-pr-workflow
description: "Full PR lifecycle — branch, commit, open PR, monitor CI, auto-fix, merge. NOT for auth setup (use github-auth) or repo management."
---

## Purpose

`github-pr-workflow` automates the complete PR lifecycle: creating branches, committing changes, opening PRs (via `gh` CLI or `git` + `curl` fallback), monitoring CI status, auto-fixing failures, and merging. It detects whether `gh` is available and chooses the right tooling automatically.

## Why This Works

**Concept 1: Automatic tool detection prevents redundant fallback logic.** The workflow checks `gh` availability once at the start and branches accordingly. This avoids embedding `gh`-specific commands that would fail silently when `gh` is absent, and avoids writing raw API calls when the CLI is available.

**Concept 2: REST API fallback makes the workflow portable.** `gh` requires separate installation and authentication setup. Using `curl` with `GH_TOKEN` as fallback means the workflow works anywhere — CI runners, containers, or bare-metal servers — as long as a GitHub token is available.

**Concept 3: CI monitoring with auto-fix prevents stale PRs.** Unfixed CI failures cause PRs to sit open for days. Automated polling + fix-commit-on-failure shortens the feedback loop from "notify the author and wait" to "fix and re-submit in minutes."

## Examples

**Good:** User says "create a PR for this feature" → workflow checks `gh` (installed) → `gh` creates branch `feat/20260602093045` → commits staged changes → opens PR with title and body → monitors CI status in a loop (polling every 30s, timeout 5 min) → CI passes → `gh pr merge <num> --squash --delete-branch`.

**Good:** `gh` is not installed (CI runner) → workflow falls back to `git` + `curl` → extracts `OWNER/REPO_NAME` from `git remote get-url origin` → creates branch via `git` → opens PR via `POST /repos/:owner/:repo/pulls` — same result, different implementation.

**Good:** CI fails with a lint error → workflow detects the failure state → creates a new commit fixing the lint issue → `git push --force-with-lease` to update the PR → re-checks CI status → continues on green.

## Anti-Patterns

**Anti-Pattern 1: Hardcoding gh CLI commands without a fallback.** Assuming `gh` is always available leads to silent failures in CI runners, fresh dev environments, or containers. Always detect and fall back.

**Anti-Pattern 2: Creating PRs with empty or placeholder descriptions.** A PR with "fix bug" or no body forces reviewers to guess the intent. Always validate the title and body before calling the API — generate them from the commit history or spec.

**Anti-Pattern 3: Pushing force after auto-fix without --force-with-lease.** Plain `git push --force` destroys any commits another contributor may have pushed to the same branch. Always use `--force-with-lease` to fail if the remote has diverged.

**Anti-Pattern 4: Infinite CI polling without a timeout.** CI can hang silently (queued, cancelled, or infrastructure failure). Always set a polling timeout (e.g., 10 minutes with 30s intervals) and report "timed out" rather than polling forever.

## When NOT to Use

- **GitHub authentication setup** — Use `github-auth` skill to configure `gh` auth or set `GH_TOKEN` first.
- **Repository creation/forking/management** — Use `github-repo-management` for repo-level operations.
- **Code review without PR context** — Use `github-code-review` for analyzing git diffs without opening a PR.
- **WIP or exploratory branches** — Opening a formal PR for throwaway experiments creates noise in the reviewer queue. Use a draft PR or skip the workflow entirely.

## Cross-References

- **github-auth** (skills/github/github-auth/SKILL.md) — Set up `gh` authentication or `GH_TOKEN` before running this workflow. Run this first if `gh auth status` fails.
- **github-code-review** (skills/github/github-code-review/SKILL.md) — After the PR is open, use this skill for the actual review workflow: analyzing diffs, running linters, and requesting changes.
- **requesting-code-review** (skills/software-development/requesting-code-review/SKILL.md) — Pre-commit verification pipeline to run *before* opening a PR. Catches issues before they enter the PR review cycle.
