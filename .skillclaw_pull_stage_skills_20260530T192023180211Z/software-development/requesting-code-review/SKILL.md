---
name: requesting-code-review
description: "Pre-commit verification pipeline — static security scan, baseline-aware quality gates, independent reviewer subagent, and auto-fix loop. Triggered by 'commit', 'push', 'ship', 'verify', 'review', 'merge', or 'pre-commit'. Use after code changes and before committing, pushing, or opening a PR. NOT for: WIP commits, documentation-only changes, casual commits, simple typo fixes, or when you explicitly want a human reviewer to handle everything end-to-end."
category: general
skill_category: pre-commit
...
---

## Pipeline Overview


┌──────────────────────────────────────────────────────┐
│              Pre-Commit Review Pipeline               │
├──────────────────────────────────────────────────────┤
│  1. Security Scan  │  2. Quality Gates  │  Continue │
│     (bandit +        │  (compare against    │  if ALL   │
│      secrets)        │   baseline metrics)  │  pass     │
├──────────────────────────────────────────────────────┤
│  3. Independent     │  4. Auto-Fix Loop    │           │
│     Reviewer         │  (re-run if fixes    │           │
│     (subagent)       │   applied)            │           │
└──────────────────────────────────────────────────────┘


## Phase 1: Static Security Scan

Run **before** any other checks. Fail fast on critical issues.

bash
# Secrets detection (high priority)
bandit -r . -f json -o bandit-report.json 2>/dev/null || true
git diff --staged | detect-secrets scan 2>/dev/null || true

# If critical severity found → BLOCK with clear message


### Bandit Severity Mapping

| Severity | Action |
|----------|--------|
| HIGH     | Block and report immediately |
| MEDIUM   | Warn but continue |
| LOW      | Log only |

### Common Security Issues to Catch

- Hardcoded credentials / API keys / tokens
- SQL injection vectors (string concatenation in queries)
- Use of `eval()`, `exec()`, `os.system()` with user input
- Insecure temporary file creation (`mktemp` without `mktemp -u`)
- Path traversal risks (`open()` with unsanitized paths)
- Disabled security features (`no-setuid`, `no-chmod` warnings)

## Phase 2: Baseline-Aware Quality Gates

Compare current change against the **baseline** (main or last release).

### Diff Stats Gate

bash
git diff --stat BASE_BRANCH...HEAD


| Metric | Gate |
|--------|------|
| Files changed | Warn if > 20 |
| Lines added | Warn if > 500 |
| Lines deleted | Warn if > 300 |
| Test coverage | Warn if coverage drops > 5% |

### Quality Threshold Checks

bash
# Complexity check
radon cc -a . | awk -F: '$2 > 10' 

# Maintainability index
radon mi -a . | awk -v limit=65 '$2 < limit'

# If any check fails → require explicit justification


## Phase 3: Independent Reviewer Subagent

**Trigger a separate agent** with fresh context. This is critical — do NOT self-review.

Delegate to subagent:
- Focus: spec compliance + code quality
- Access: full diff + spec
- Instruction: If issues found → list them with file:line references

### Review Checklist

- [ ] Does the change match the spec/acceptance criteria?
- [ ] Are there missing test cases for new logic?
- [ ] Are error cases handled gracefully?
- [ ] Is the diff focused (no scope creep)?
- [ ] Are there clear commit messages?

### If Reviewer Finds Issues

1. Report each issue with **file:line** reference
2. Do NOT auto-fix without explicit user approval
3. Group related issues
4. Prioritize: Security > Correctness > Style

## Phase 4: Auto-Fix Loop

Only runs **if Phase 3 found no blocking issues** but found fixable style/minor issues.

bash
# Auto-format if pre-commit hooks are configured
pre-commit run --all-files 2>/dev/null || true

# Re-run quality gates after auto-fix
# If still failing → report and stop


### Auto-Fixable Issues

- Formatting (black, gofmt, prettier)
- Import sorting (isort)
- Trailing whitespace
- Missing newlines at EOF

### Non-Auto-Fixable Issues

- Logic errors
- Missing tests
- Security vulnerabilities
- API contract changes

## Quick Reference

| Situation | Action |
|-----------|--------|
| User says "commit" / "push" / "ship" | Run full pipeline |
| User says "review before merge" | Run Phases 1-3 only |
| High-risk change (>10 files, >500 lines) | Run all phases, require explicit approval |
| Critical security issue found | Block immediately, report |

## Common Rationalizations

| Rationalization | Reality |
|----------------|---------|
| "This is a small change, I don't need a full review" | Small changes cause the largest incidents — review prevents regressions |
| "I tested it locally, it's fine" | Local testing doesn't catch integration issues or compare against the full codebase baseline |
| "CI will catch any problems" | CI runs tests, not quality or security reviews — it won't catch logic errors or spec drift |
| "I just fixed a typo" | Typos in critical paths (auth, validation, queries) can be security vulnerabilities |
| "The change is already reviewed in a PR" | Pre-commit review catches issues before they enter the commit history |
