---
name: github-issues
description: "Create, manage, triage, and close GitHub issues. Search existing issues, add labels, assign people, and link to PRs. Works with gh CLI or falls back to git + GitHub REST API via curl."
tags: [github, issues, project-management, gh-cli, api]
related_skills: [github-pr-workflow, github-code-review, github-auth, github-issues]
---

## Purpose

Managing GitHub issues programmatically from the command line is essential for automating project management workflows — creating bug reports, triaging incoming requests, assigning work, and linking issues to PRs. This skill covers both the `gh` CLI (convenient, handles auth) and the raw GitHub REST API via `curl` (works in headless environments, CI pipelines, and when `gh` isn't installed). The core workflow follows a consistent pattern: detect available auth method → map user intent to API action → execute → confirm result.

## Teaching: Why This Works

### Two-Phase Auth Detection

The skill auto-detects whether `gh` CLI is authenticated, falling back to `GITHUB_TOKEN`-based REST API calls. This means you can use the same mental model regardless of environment — the skill adapts transparently.

### Shared API Model

GitHub Issues and Pull Requests share the same REST API endpoint (`/repos/{owner}/{repo}/issues`) but are distinguished by the `pull_request` field. Understanding this quirk prevents confusion when an issue query also returns PRs.

### gh CLI vs curl: When Each Shines

| Tool | Best for | Limitation |
|------|----------|------------|
| `gh` CLI | Interactive use, auto-auth, pagination | Not available in some CI/containers |
| curl | Headless/CI, custom GitHub Enterprise hosts, fine-grained control | Manual pagination, needs token |

## Examples

### Example 1: Automated Bug Triage Pipeline

**Scenario:** A CI job detects test failures and needs to automatically create a GitHub issue with structured labels.

**Approach:**
```bash
# In a CI script (no gh CLI), create a bug report automatically
export GITHUB_TOKEN=${GITHUB_TOKEN:?}

curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "CI: Nightly test suite failed (2026-06-01)",
    "body": "## Failed Tests\n- test_auth_login (5 failures)\n- test_api_grants (3 failures)\n\nSee CI run: $CI_JOB_URL",
    "labels": ["bug", "ci", "priority:high"],
    "assignees": ["oncall-eng"]
  }' \
  "https://api.github.com/repos/myorg/myrepo/issues"
```

**Outcome:** Bug issue created with labels and assignee in under 2 seconds. The structured body includes trace information for the on-call engineer.

### Example 2: Weekly Issue Triage with gh CLI

**Scenario:** As a maintainer, you want to review all unlabelled issues and categorize them for the weekly triage meeting.

**Approach:**
```bash
# Find issues without labels
gh issue list --repo owner/repo --state open --json number,title,labels --jq '.[] | select(.labels | length == 0) | .number'

# Batch-add labels to multiple related issues
for num in 42 43 47 51; do
  gh issue edit "$num" --repo owner/repo --add-label "triage:needs-priority"
done

# Assign to sprint milestone
gh issue edit 42 --repo owner/repo --milestone "Sprint 24"
```

**Outcome:** 4 issues labelled and assigned to a milestone in a single script iteration. Previously this required clicking through the web UI for each issue.

### Example 3: Linking PRs to Issues

**Scenario:** After merging a fix, you want to close both the fix PR and the original issue it references, then verify.

**Approach:**
```bash
# Auto-close issue when closing PR (uses keywords in PR body)
gh pr close 456 --delete-branch

# Or manually close the issue with a reference note
gh issue close 123 --repo owner/repo --comment "Fixed in PR #456 — verified in staging"
```

**Outcome:** Clean traceability between fix and issue. The `gh issue close --comment` flag adds a closing note that appears in the issue timeline.

## Common Anti-Patterns

### 🔴 Treating Issues and PRs as Separate in the API
The GitHub API returns **both issues and PRs** from the `/issues` endpoint. A query like `GET /issues?state=open` will return PRs mixed in. Filtering by `labels` or using `type:issue` in search queries is essential for accurate results.

**Fix:** In search queries, use `type:issue` qualifier: `gh issue search "bug type:issue"`. Or filter by absence of `pull_request` key in curl responses.

### 🔴 Hardcoding the Token in Scripts
Embedding `GITHUB_TOKEN=ghp_xxx` directly in scripts is a security risk — it can leak via shell history, CI logs, or accidental commits. Use environment variables or secret managers instead.

**Fix:** Use `export GITHUB_TOKEN="${GITHUB_TOKEN:?}"` and set the token externally (CI secret store, `.env` file, 1Password CLI). Never hardcode tokens.

### 🔴 Ignoring Pagination
The GitHub API returns a maximum of 30 items per page by default. If your repo has 100+ open issues, `gh issue list` without `--page` will miss most of them.

**Fix:** Use `gh issue list --limit 100` or `gh issue list --page 1 --per-page 100` (max 100 per page). For curl, use `?per_page=100&page=N` and check the `Link` header for pagination URLs.

### 🔴 Forgetting Rate Limits
Unauthenticated requests are limited to 60/hour. Authenticated requests get 5,000/hour but can be exhausted quickly in automated scripts, especially loops.

**Fix:** Always use authentication (`gh auth status` or `GITHUB_TOKEN`). Check `X-RateLimit-Remaining` header. For batch operations, add delays between requests: `sleep 1` in loops.

## When NOT to Use This Skill

- **For managing non-GitHub issues** (GitLab, Jira, Linear, Trello) — use their respective APIs or dedicated tools
- **For pull request operations** (review, merge, CI checks) — use `github-pr-workflow` instead
- **For GitHub authentication setup** — use `github-auth` skill for first-time auth configuration
- **For code review workflows** — use `github-code-review` for inline PR comments and diffs
- **For repo management** (create, fork, configure repos) — use `github-repo-management`
- **For batch operations on thousands of issues** — the API has rate limits; use GraphQL `gh api graphql` for bulk mutations

## Cross-References

- [github-pr-workflow](/skills/github/github-pr-workflow/SKILL.md) — Full PR lifecycle: create, review, merge
- [github-code-review](/skills/github/github-code-review/SKILL.md) — Code review with inline comments and diffs
- [github-auth](/skills/github/github-auth/SKILL.md) — Set up GitHub authentication for CLI and API
- [github-repo-management](/skills/optional-skills/github-repo-management/SKILL.md) — Create, fork, and configure repos
- [linear](/skills/optional-skills/linear/SKILL.md) — Alternative issue tracker via GraphQL API
