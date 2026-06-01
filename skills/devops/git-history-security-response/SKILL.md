---
name: git-history-security-response
description: "Use when responding to sensitive data exposure in git history — API keys, tokens, credentials, or business data accidentally pushed to a public repository. Also use for proactive security audits of git history to detect leaked secrets before incidents occur. Covers tracing commit ancestry with `git log --all -S`, BFG Repo-Cleaner, git-filter-repo, cherry-picking clean commits, and force-pushing to erase history. NOT for: routine commits, normal git workflows, or when the repository has no sensitive data history."
category: devops
---

## Teaching (Why This Works)

Git history is a directed acyclic graph (DAG) of immutable commits. When sensitive data is pushed, it **cannot be deleted** — it can only be **rewritten** by generating new commit objects that exclude the sensitive content. Understanding this fundamental constraint is essential: cleanup isn't about removing data but about replacing the entire history lineage.

This skill exists because:
- **Secret scanning tools** (GitHub, GitLab) flag exposed credentials but don't remove them
- **A single leaked API key** can cost thousands in cloud bills within hours (automated scanners find exposed keys in minutes)
- **git filter-branch is deprecated** — using BFG or git-filter-repo is 10-1000x faster and safer
- **Incident response** for git leaks requires coordinated action: identify → contain → remediate → verify → notify

## Anti-Patterns

### 🚫 Force Push Without Team Coordination
Blindly force-pushing after history rewrite destroys your teammates' local branches. Always coordinate a "rebase window" — announce the rewrite, have everyone commit/stash, then all rebase onto the cleaned branch.

### 🚫 Only Cleaning the Main Branch
Secrets often exist on feature branches, tags, or orphaned branches. `git log --all` reveals the full scope. Cleaning only `main` leaves the secret accessible via `git fetch origin refs/heads/feature-branch`.

### 🚫 Assuming Rewrite = Complete Removal
GitHub caches commit data, forks duplicate the content, and CI artifacts may retain the commit. After rewriting:
1. Revoke the credential first (still usable if cached)
2. Check GitHub for cached copies (Support can purge)
3. Notify fork owners
4. Rotate all credentials that appeared in any touched commit

### 🚫 Using filter-branch for Large Repos
`git filter-branch` creates a shell process per commit — a 2000-commit repo runs 2000 shell invocations. BFG (JVM-based, bulk processing) does the same work in a single pass, 10-1000x faster. `filter-branch` is officially deprecated; use `git-filter-repo` or BFG.

## Examples

### Example 1: Accidental .env Push (Real-World Scenario)
**Situation**: A developer pushes a commit containing `.env` with AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.

**Bad approach**: Directly force-push a revert commit.
```bash
git revert HEAD
git push --force  # WRONG — the secret is still in the reverted commit's history
```

**Correct approach**:
```bash
# 1. Immediately revoke the keys in AWS IAM
# 2. Remove .env from all history
pip install git-filter-repo
git filter-repo --path .env --invert-paths
# 3. Verify
git log --all -S "AKIA" --oneline  # Should return empty
# 4. Coordinate with team, then force push
git remote add origin <url>
git push origin --force --all
```

**Verification**: After cleanup, running `git log --all --diff-filter=A -- .env` returns no matches.

### Example 2: Old Credentials Found Across 50+ Commits
**Situation**: A security audit finds a hardcoded database password (`password=TopSecret2023`) across 47 commits spanning 3 branches and 2 tags.

**Bad approach**: Manual cleanup commit by commit (hours of work, error-prone).

**Correct approach**:
```bash
# BFG bulk replacement (seconds, not hours)
java -jar bfg.jar --replace-text passwords.txt --no-blob-protection repo.git
# passwords.txt contains: TopSecret2023###
git push origin --force --all
git push origin --force --tags
```

**Result**: All 47 commits rewritten in under 5 seconds. Each commit hash changes, but tree content (minus the password) is preserved.

### Example 3: Prevention via Pre-Push Hook
**Situation**: Team wants to prevent future leaks without manual policing.

```bash
cat > .git/hooks/pre-push << 'EOF'
#!/bin/bash
# Block push if common secret patterns are in staged changes
if git diff --staged -S "sk-" -- . > /dev/null 2>&1; then
  echo "❌ BLOCKED: Potential OpenAI API key (sk-...) in staged changes"
  exit 1
fi
if git diff --staged -S "ghp_" -- . > /dev/null 2>&1; then
  echo "❌ BLOCKED: Potential GitHub PAT (ghp_...) in staged changes"
  exit 1
fi
EOF
chmod +x .git/hooks/pre-push
```

## When NOT to Use

- **Forks exist** — If other users have forked the repo, rewriting your history won't reach their forks. You must notify fork owners and request they delete/update their forks.
- **Compliance/audit requirements** — If regulations require an immutable audit trail (e.g., PCI-DSS, SOX), use credential revocation + `.gitignore` instead of history rewriting. Document the incident separately.
- **Simple rollback needed** — If no sensitive data was committed (e.g., you just want to undo a bad merge), use `git revert` or `git reset`, not history rewriting.
- **Large binary assets** — `git filter-repo` struggles with large blobs. For secrets embedded in binaries (images, compiled files), use BFG's `--strip-blobs-bigger-than` or block via `.gitattributes`.
- **Public mirrors exist** — If the repo is mirrored on GitLab, Bitbucket, or other services, rewriting GitHub won't clean the mirrors.

## Cross-References

- **[credential-pattern-replacement](../security/credential-pattern-replacement/SKILL.md)** — Systematically replacing masked/redacted credentials in config files across the stack
- **[codebase-inspection](../software-development/codebase-inspection/SKILL.md)** — LOC counting and static analysis to detect potential secret exposure
- **git-secret-audit** — Automated scanning for leaked API keys, tokens, and credentials in git repos (available as an external tool)
- **[systematic-debugging](../software-development/systematic-debugging/SKILL.md)** — Methodical troubleshooting approach applicable to security incident investigation
- **[docker-management](../infrastructure/docker-management/SKILL.md)** — Managing containers that may need credential rotation after a leak

## Quick Reference

When sensitive data is accidentally pushed:

1. **Identify** the sensitive content and the commit(s) that introduced it
2. **Assess** the exposure scope (public repo? forks? clones?)
3. **Contain** by revoking exposed credentials immediately
4. **Remediate** by rewriting history and force-pushing clean commits
5. **Notify** affected parties if data is truly public

## Proactive Security Audit

Run these checks regularly or before any public repo push to catch leaked secrets before they are found by others.

### Audit entire history for common secret patterns

```bash
# AWS keys
git log --all -S "AKIA" --oneline

# GitHub tokens
git log --all -S "ghp_" --oneline
git log --all -S "github.com" --oneline | grep -i "token\|key\|secret"

# OpenAI keys
git log --all -S "sk-" --oneline

# Database passwords
git log --all -S "password=" --oneline

# JWT/Bearer tokens
git log --all -S "eyJ" --oneline

# Private keys
git log --all -S "-----BEGIN" --oneline

# Check for .env committed
git log --all --oneline -- ".env"

# Scan all branches
git log --all --oneline | head -20

# Check remote URLs for embedded credentials
git remote -v
```

### .gitignore coverage check

```bash
grep -i "\.bak" .gitignore || echo "WARNING: .bak not in .gitignore"
grep -i "\.env" .gitignore || echo "WARNING: .env not in .gitignore"
grep -i "secrets" .gitignore || echo "WARNING: secrets/ not in .gitignore"
```

### Commit hygiene checks

```bash
git log origin/main..HEAD --oneline
git log origin/main..HEAD --oneline -- "skills/" | head -20
```

## Incident Response

### Find secrets in history

```bash
# Trace a specific string through all history
git log --all -p -S "YOUR_SECRET_VALUE" --source --all

# Case-insensitive search
git log --all -p -S "your_secret" --source --all -i

# Search for API key patterns across all commits
git log --all -p --pattern "sk-[0-9a-zA-Z]" | head -100
git log --all -p --pattern "ghp_[0-9a-zA-Z]" | head -100
git log --all -p --pattern "AKIA[0-9A-Z]" | head -100

# Grep all commits for secret keyword
grep -r "secret" --all-commit -- . 2>/dev/null
```

### Remove a secret from all history

**WARNING: These operations rewrite git history. Coordinate with your team before proceeding.**

**Option A: BFG Repo-Cleaner (recommended, 10-1000x faster than filter-branch)**

Download from https://rtyley.github.io/bfg-repo-cleaner/

```bash
# Create passwords.txt with lines like "SECRET_KEY###" (appends ### to replacement)
echo "THE_SECRET_VALUE###" > passwords.txt

# Clean the repository
java -jar bfg.jar --replace-text passwords.txt --no-blob-protection repo.git

# Force push to overwrite remote
git push origin --force --all
git push origin --force --tags
```

**Option B: git-filter-repo (requires pip install)**

```bash
pip install git-filter-repo
git filter-repo --path-glob '*.env' --invert-paths
git filter-repo --path secret.txt --invert-paths
```

**Option C: Cherry-pick clean commits**

```bash
git checkout --orphan clean-history
git cherry-pick <clean-commit-hash>
# Repeat for all clean commits, then force push
```

**Option D: git filter-branch (legacy, slower)**

```bash
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch filename_with_secret' \
  --prune-empty --tag-name-template '' -- --all
```

### Verify cleanup

```bash
git log --all -S "YOUR_SECRET" --oneline  # Should return empty
grep -r "YOUR_SECRET" --all-commit -- . 2>/dev/null  # Should return empty
```

### Check exposure scope

```bash
# GitHub: check if repository was public
gh api repos/OWNER/REPO --jq '.visibility'

# Check recent activity
gh api repos/OWNER/REPO/events --jq '.[].type'
```

### After force-push to GitHub

GitHub shows commit remediation status. Check **Settings → Code security and analysis → Secret scanning** for alert details.

## Notify Affected Parties

- If a GitHub PAT was exposed: revoke immediately at https://github.com/settings/tokens
- If an AWS key was exposed: rotate in IAM console and check CloudTrail for misuse
- If a database password was exposed: rotate and audit access logs

**Notification Template:**

**Subject:** [Security Incident] Repository {name} - Sensitive Data Exposure

**Details:**
- What was exposed:
- When it was exposed:
- Exposure scope (public forks, downloads):
- Action taken:
- Credentials revoked: Yes/No

## Prevention

### Pre-push hook

```bash
# .git/hooks/pre-push
#!/bin/bash
git diff --staged -S "sk-" -- . && echo "BLOCKED: potential secret in staged changes" && exit 1
git diff --staged -S "ghp_" -- . && echo "BLOCKED: potential GitHub token in staged changes" && exit 1
git diff --staged -S "AKIA" -- . && echo "BLOCKED: potential AWS key in staged changes" && exit 1
```

### Additional measures

- Use git-secret, blackbox, or similar tools for encrypting sensitive files in repos
- Enable secret scanning on GitHub: **Settings → Code security and analysis → Secret scanning**
- Enable push protection: **Settings → Code security and analysis → Push protection**