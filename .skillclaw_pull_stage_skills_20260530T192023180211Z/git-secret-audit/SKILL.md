---
name: git-secret-audit
description: "Scans a git repository for leaked API keys, tokens, credentials, and other secrets. Covers: unpushed commit audit, git history forensics via git log -S, unreachable blob inspection, .gitignore coverage verification, and pre-commit hook validation. NOT for: scanning repositories you do not own or have permission to audit, general-purpose secret scanning tools (use dedicated tools instead), or non-git version control systems."
category: general
---

## Audit Strategy

Run these steps in order. Each step is read-only and safe to run.

## Step 1: Unpushed Commits

bash
git log origin/main..HEAD --oneline
git log origin/develop..HEAD --oneline  # if using develop branch


If origin/main doesn't exist:
bash
git branch -r


Inspect each unpushed commit for secrets before pushing.

## Step 2: Git History Forensics

Use `git log -S` to search for strings that were added or removed from any file's history. This is faster than grep across all history and finds commits that later rewrote the secret.

bash
# Search for common secret patterns
git log --all -S "sk-" --oneline

git log --all -S "ghp_" --oneline

git log --all -S "AKIA" --oneline       # AWS access key prefix
git log --all -S "-----BEGIN" --oneline

git log --all -S "password=" --oneline

git log --all -S "api_key" --oneline

git log --all -S "token" --oneline


For each hit, inspect the full diff:
bash
git show <commit-hash>


## Step 3: .gitignore Verification

Verify that directories and files containing real credentials are properly excluded:

bash
cat .gitignore


Key patterns to check for:
- `evolver/` or `.evolver/` — contains .env with real keys
- `*.env` — environment variable files
- `secrets/`, `credentials/`, `keys/`
- `*.pem`, `*.key`, `*.p8`
- `.env*`, `.secrets*`

If missing, add them before committing.

## Step 4: Pre-commit Hook Validation

Check if pre-commit hooks are in place:

bash
git ls-files | grep -E "hooks/|pre-commit"
cat .git/hooks/pre-commit 2>/dev/null || echo "No pre-commit hook found"


If no hook exists, consider adding one that scans for credential patterns before commit.

## Step 5: Unreachable Objects

Check for blobs that exist in the object store but are not referenced by any branch or tag:

bash
git fsck --unreachable --no-reflogs


Review any reported unreachable blobs for secrets. Note: this may include legitimate untracked files that were once committed and then removed.

## Step 6: False Positive Discrimination

Distinguish real secrets from test/placeholder patterns:

| Pattern | Real Secret? | Notes |
|---|---|---|
| `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` | YES | Real GitHub PAT |
| `ghp_xxxx...xxxx` (truncated, test-like) | NO | Placeholder |
| `sk-prod-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` | MAYBE | MiniMax / OpenAI style |
| `sk-test-...` | NO | Explicitly test |
| `evolver/.env` | YES | Real .env file |
| `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` with 37+ chars | YES | GitHub PAT |

## Step 7: Confirm No Real Secrets Remain

After remediation, re-run Steps 1 and 2 to confirm clean state.

