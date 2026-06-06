---
name: github-pr-workflow
description: "Full pull request lifecycle — create branches, commit changes, open PRs, monitor CI status, auto-fix failures, and merge. Works with gh CLI or falls back to git + GitHub REST API via curl. Trigger signals: user asks to create a PR, open a pull request, merge code, check CI status, fix CI failures, sync branches. NOT for: GitHub authentication setup (use github-auth), repository creation/forking/management (use github-repo-management), code review without PR context (use github-code-review)."
category: general
---

## GitHub PR Workflow

### Prerequisites

**gh CLI (preferred):** `brew install gh` or `npm install -g gh`
**Fallback:** `git`, `curl`, `jq`, and `GH_TOKEN` env var set to a GitHub Personal Access Token

### Detection Flow


if gh is installed and gh auth status succeeds:
    use gh CLI for all operations
else:
    use git + GitHub REST API via curl
    require GH_TOKEN env var
    require REPO_OWNER and REPO_NAME env vars (or extract from git remote)


## Branch & Commit Workflow

### Via gh CLI

bash
# Create a branch and commit
BRANCH="feat/$(date +%Y%m%d%H%M%S)"
git checkout -b $BRANCH
git add . && git commit -m "..."
git push -u origin $BRANCH

# Create PR
gh pr create --title "<title>" --body "<description>" --base <target-branch>
gh pr view --web  # open in browser


### Via curl fallback

bash
# Detect repo from git remote
REPO=$(git remote get-url origin | sed 's|.*github.com/||' | sed 's|\.git$||')
OWNER=$(echo $REPO | cut -d/ -f1)
REPO_NAME=$(echo $REPO | cut -d/ -f2)

# Create branch
BRANCH="feat/$(date +%Y%m%d%H%M%S)"
git checkout -b $BRANCH
git add . && git commit -m "..."
git push -u origin $BRANCH

# Create PR via REST API
curl -s -X POST \
  -H "Authorization: token $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/$OWNER/$REPO_NAME/pulls \
  -d '{"title":"<title>","body":"<description>","head":"'$BRANCH'","base":"<target>"}'


## CI Monitoring & Auto-Fix

### Check CI status

bash
# gh
gh pr status
gh pr checks <pr-number>

# curl fallback
curl -s -H "Authorization: token $GH_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO_NAME/commits/$BRANCH/status"


### Auto-fix CI failures

bash
# Checkout PR branch
gh pr checkout <pr-number>
# Fix failures locally, amend or create new commit
git commit --amend --no-edit
git push --force-with-lease


## Merge

bash
# gh
gh pr merge <pr-number> --squash --delete-branch

# curl fallback
curl -s -X PUT \
  -H "Authorization: token $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/$OWNER/$REPO_NAME/pulls/<pr-number>/merge" \
  -d '{"merge_method":"squash"}'


## Push Fallback Patterns

### When origin push fails with "403/Permission denied"

If `git push -u origin $BRANCH` fails because you don't have write access to the upstream repo (e.g., pushing to someone else's repo):

```bash
# 1. Check if a fork already exists
gh repo fork <owner>/<repo> --clone=false

# 2. List existing remotes
git remote -v
# → origin  https://github.com/<owner>/<repo>.git (fetch)
# → origin  https://github.com/<owner>/<repo>.git (push)  ← DENIED

# 3. Add your fork as a remote
#    If you already forked earlier, find the clone URL on github.com/<your-user>/<repo>
git remote add fork https://github.com/<your-user>/<repo>.git

# 4. Push to the fork's branch
git push -u fork $BRANCH

# 5. Create PR from fork (works because your fork is writable)
gh pr create --title "<title>" --body "<description>" --base <target-branch> --repo <owner>/<repo>

# Or via curl
curl -s -X POST \
  -H "Authorization: token $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/<owner>/<repo>/pulls \
  -d '{"title":"<title>","body":"<description>","head":"<your-user>:'$BRANCH'","base":"<target>"}'
```

**Common causes of origin push denial:**
- **No write access**: you're not a collaborator on the repo → must use fork
- **Branch protection**: the base branch (main/master) is write-protected → branch rules don't block your feature branch, but you CANNOT push to protected branches directly
- **Expired token**: `GH_TOKEN` is stale → regenerate from GitHub Settings → Developer settings → Personal access tokens
- **Wrong remote URL**: `git remote -v` shows `https` but you need `git@` (SSH), or vice versa; credentials differ between protocols

### When upstream branch protection blocks force-push

Protected branches (main, master, release/*) reject `git push --force-with-lease`. Push to a non-protected feature branch instead, then open a PR:

```bash
# Can't force-push to main? Push to a feature branch
git branch temp-fix/$(date +%Y%m%d)
git checkout temp-fix/$(date +%Y%m%d)
git push -u origin temp-fix/*

# Open PR from the temp branch
gh pr create --title "<title>" --body "<description>" --base <protected-branch>
```

## Quality Guidelines

- Check gh availability first, then fall back to git+curl. Do NOT assume gh is installed.
- PR descriptions and branch names must be validated before creation to avoid silent failures.
- CI status polling should include a timeout to prevent infinite loops.
- Auto-fix logic must identify the specific failing step before attempting remediation.
- API rate limiting: 5000 req/hr for authenticated requests
- When push fails, ALWAYS check `git remote -v` first — the cause (permission vs protocol vs URL typo) is visible in the remote list.
