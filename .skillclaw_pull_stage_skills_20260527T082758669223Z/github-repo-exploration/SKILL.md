---
name: github-repo-exploration
description: "Efficiently explore GitHub repository structure and content using the GitHub API or `gh` CLI. NOT for: browsing GitHub issues/comments, code review workflows, or CI/CD automation — use specialized skills for those. For: understanding repo structure, reading README, finding key files, exploring directory trees, and extracting content for analysis."
category: general
---

# GitHub Repository Exploration Pattern

When asked to explore a GitHub repository, use the GitHub API or `gh` CLI — NOT browser navigation or raw.githubusercontent.com URLs.

## Why raw URLs Fail

`raw.githubusercontent.com` redirects or returns empty for private/special repos. `github.com/blob/` pages need JavaScript rendering. Browser navigation is slow and fragile.

## Preferred Method: GitHub API

bash
# Get repo metadata
gh api repos/{owner}/{repo}

# List directory contents
gh api repos/{owner}/{repo}/contents/{path}

# Get file content (base64 encoded)
gh api repos/{owner}/{repo}/contents/{path} --jq '.content' | base64 -d

# Read README
curl -s https://api.github.com/repos/{owner}/{repo}/readme | jq -r '.content' | base64 -d

# List all files recursively (tree)
gh api repos/{owner}/{repo}/git/trees/HEAD?recursive=1 | jq -r '.tree[].path'


## Read File From Local Clone

If the repo is cloned locally:
bash
cat ~/path/to/repo/README.md
grep -r "keyword" ~/path/to/repo/src/ --include="*.py"
ls -la ~/path/to/repo/


## Exploration Order

1. `gh api repos/{owner}/{repo}` — get basic info (description, default branch, language)
2. `gh api repos/{owner}/{repo}/contents/` — list root directory
3. README.md first — get project overview
4. Then explore relevant subdirectories based on the goal
5. Use `gh api .../git/trees/HEAD?recursive=1` for full file tree when needed

## Session Continuity

For multi-step exploration within a session, prefer:
- Terminal + `gh` cli (most reliable)
- GitHub API via `curl` or `requests`
- Local clone if already present

Avoid: `browser_navigate` for raw file content, `raw.githubusercontent.com` URLs, or clicking through GitHub's web UI.

## When gh is unavailable

If `gh` CLI is not authenticated or not installed, fall back to:
bash
# GitHub API with personal token
git clone https://github.com/{owner}/{repo}.git ~/tmp/{repo}
cd ~/tmp/{repo}
# explore locally


Do NOT waste tool calls trying to navigate GitHub's web interface to extract code content.
