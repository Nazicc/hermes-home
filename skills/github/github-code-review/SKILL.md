---
name: github-code-review
description: "Use when reviewing code changes by analyzing git diffs, leaving inline comments on PRs, and performing thorough pre-push review. Works with gh CLI or falls back to git + GitHub REST API via curl. NOT for: non-GitHub code review, automated testing, or when GitHub CLI is not available."
category: github
triggers:
  - review PR
  - review code
  - analyze diff
  - git diff review
  - code review
  - PR comments
  - pre-push review
anti_triggers:
  - create repository
  - manage issues
  - run tests
  - deploy code
version: 1.2.0
author: Hermes Agent
license: MIT
---

## Purpose

Perform thorough, evidence-first code reviews with clear severity tags, linking related skills when deeper analysis or fix planning is needed. Every review starts with reading the full diff — opinions come after data, not before it.

## When NOT to Use

- Non-GitHub platforms (GitLab, Bitbucket, etc.) — this skill's commands target gh CLI and GitHub REST API
- Automated CI/CD checks / linting — those run in CI, not in review
- Repository setup or issue management — use github-issues or github-repo-management instead

## Application

### Step 1: Fetch PR metadata

```bash
# Using gh CLI (preferred)
gh pr view <pr-number> --repo <owner>/<repo> --json title,body,state,author

# Using GitHub REST API
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/<owner>/<repo>/pulls/<pr-number>
```

### Step 2: Get the full diff (evidence-first)

```bash
gh pr diff <pr-number> --repo <owner>/<repo>

# Or via API
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/<owner>/<repo>/pulls/<pr-number> \
  | jq -r '.diff_url' | xargs curl -H "Authorization: token $GITHUB_TOKEN"
```

**ALWAYS read the full diff before forming any opinion.** Do not pre-judge based on description or title.

### Step 3: Analyze each changed file

Check in order of priority:
1. **Correctness** — logic errors, off-by-one, null safety, edge cases
2. **Security** — injection, auth bypass, data exposure, hardcoded secrets
3. **Test coverage** — are the new/changed paths tested? Are edge cases missing?
4. **Performance** — N+1 queries, unnecessary allocations, hot-path regressions
5. **Maintainability** — naming, duplication, dead code, comment quality

### Step 4: Post inline comments

```bash
gh api repos/<owner>/<repo>/pulls/<pr-number>/comments \
  -f body='<comment-body>' \
  -f commit_id='<commit-sha>' \
  -f path='<file-path>' \
  -f line=<line-number>
```

**Tag every comment with severity:**
- `[BLOCKING]` — must fix before merge (bug, security, data loss)
- `[SUGGESTION]` — nice to have, non-blocking (style, naming, minor refactor)
- `[QUESTION]` — need clarification on intent

### Step 5: Submit overall review

```bash
gh pr review <pr-number> --repo <owner>/<repo> --approve  # or --request-changes

# Via API
curl -X POST -H "Authorization: token $GITHUB_TOKEN" \
  -d '{"event": "APPROVE", "body": "LGTM"}' \
  https://api.github.com/repos/<owner>/<repo>/pulls/<pr-number>/reviews
```

## Evidence-First Methodology

1. **Fetch data first** — pull the diff before reading title/description/body. The code tells the truth.
2. **Isolate the opinion** — write down what the diff changes before deciding if it's good or bad.
3. **Prove or disprove** — for each concern, trace the actual code path. If you can't trace it, it's not a finding.
4. **Cite line numbers** — every comment references a specific line. No "somewhere in this file" comments.

## Anti-Patterns

1. **Opinion-before-evidence** — Forming a review opinion after reading only the PR title/description. Common trap: "this looks like a security issue" before confirming the code path exists. Read the diff first, then form opinions.

2. **Rubber-stamping similar changes** — Approving repetitive patterns (e.g., "add field to DTO + mapper + response") without checking each instance. Same root cause can produce the same bug — inspect each instance individually.

3. **Scope creep** — Requesting non-blocking refactors in a correctness review, or blocking on style in a draft PR. Tag severity clearly and never mix BLOCKING and SUGGESTION in the same comment.

4. **Ignoring test coverage** — Skipping test files in the diff. If the PR has no test changes, flag it. If tests exist but don't cover the new edge case, flag it too.

5. **Nit-only reviews** — Twenty style comments and missing the logic bug. Prioritize correctness and security. One blocking finding is worth more than ten nits.

## Examples

**Good review comment:**
> `[BLOCKING]` Line 42: `user.email` is used directly in the SQL query. This is susceptible to SQL injection. Use parameterized queries (`cursor.execute("SELECT * FROM users WHERE email = %s", (email,))`) instead.

**Bad review comment:**
> This function name should be camelCase instead of snake_case. Also, the SQL might have issues.

## Edge Cases

- **Large diffs**: Paginate using `per_page` and `page` parameters; process in chunks
- **Binary files**: Skip binary file diffs — they cannot be reviewed via text diff
- **Renamed files**: Use `git diff --name-status` to detect renames before reviewing
- **Merge commits**: Exclude merge commits from diff review (`--no-merges`)
- **Unrelated commits in PR**: Filter by commits belonging to the PR vs. base branch history
- **gh not installed**: Fall back to `git fetch` + `git diff origin/<branch>` + `curl` to GitHub REST API
- **Authentication**: Set `GITHUB_TOKEN` environment variable for API calls; gh CLI uses stored credentials

## Cross-References

- **systematic-debugging** — After finding a bug in review, use the 4-phase process to trace root cause before suggesting a fix
- **writing-plans** — For PRs needing structural changes, create a fix plan instead of listing disconnected comments
- **spec-driven-development** — When a PR introduces behavior that should have been spec'ed first, reference for spec-first workflow
- **deerflow-commander** — Delegate deep research on unfamiliar dependencies or patterns encountered in the diff
