---
name: github-auth
description: "Set up GitHub authentication for the agent using git (universally available) or the gh CLI. Covers HTTPS tokens, SSH keys, credential helpers, and gh auth — with a detection flow to pick the right method automatically.\n\n**Use when:**\n- User asks to authenticate with GitHub, set up git credentials, or configure GitHub access\n- git push/pull fails with authentication error (e.g. 'Authentication failed', 'Permission denied')\n- Agent needs to push to a private GitHub repo and no credentials are cached\n- Starting work in a new repo that requires write access\n- GitHub API operations fail with 401/403 errors\n- You need to configure git credential helpers for a repository\n\n**NOT for:**\n- Read-only public repo access via HTTPS URL (no auth needed)\n- GitHub API operations when no credentials or gh CLI are present (configure auth first then retry)\n- Operations that require gh-specific interactive prompts (gh auth login)\n- General git config that has nothing to do with GitHub (use plain git config instead)\n- Browsing, cloning public repos, or read-only API queries (use git clone / GitHub REST directly)"
category: general
version: 1.1.0
...
author: Hermes Agent
...
license: MIT
...
---

## Environment Detection

Run the detection helper to determine available auth methods:

    source ~/.hermes/skills/skills/github-auth/scripts/gh-env.sh
    echo "METHOD=$GH_AUTH_METHOD"

The script checks (in order) and sets these variables:
- `GH_AUTH_METHOD`: "gh", "curl", or "none"
- `GITHUB_TOKEN`: present if a GitHub token is found
- `GH_USER`: authenticated gh user (if gh is available)

1. `gh auth status` → method=`gh`
2. `git config --global credential.helper` → method=`curl` (GitHub REST API)
3. Nothing found → method=`none`

## Quick Setup

### Option A — gh CLI (preferred when available)

    which gh && gh auth status

If authenticated, use `gh` for all operations:

    gh auth login --git-protocol https --readime

### Option B — GitHub REST API via curl (no gh, no token needed for public repos)

For public repos, git uses unauthenticated HTTPS:

    git clone https://github.com/user/repo.git

For private repos without gh, set a Personal Access Token:

    export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
    export GH_TOKEN="$GITHUB_TOKEN"
    git remote add origin https://github.com/user/repo.git
    git remote set-url origin https://$GITHUB_TOKEN@github.com/user/repo.git

### Option C — SSH key

    ssh-keygen -t ed25519 -C "your_email@example.com"
    git config --global core.sshCommand "ssh -i ~/.ssh/id_ed25519"
    # Add public key to GitHub → Settings → SSH Keys
    git remote add origin git@github.com:user/repo.git

### Option D — Git credential helper (persistent)

    git config --global credential.helper osxkeychain  # macOS
    git config --global credential.helper store         # stores in ~/.git-credentials
    # Next git push will prompt for username/token

## When All Methods Fail

**If `GH_AUTH_METHOD=none` after running gh-env.sh:**

1. **Do NOT attempt API-based GitHub operations** (creating repos, managing issues, pushing with auth-required remotes) — they will fail.
2. **For git push to existing remotes**: If the remote URL is `https://github.com/user/repo.git` without a token in the URL, the push will fail with authentication required. Ask the user to provide a `GITHUB_TOKEN` env var or set up gh CLI.
3. **For creating new GitHub repos**: This requires API access. Tell the user: "I cannot create a GitHub repo — no GitHub credentials are configured. Please create the repo at github.com and let me know the URL so I can add it as a remote."
4. **For cloning private repos**: Cannot be done without credentials. Ask the user to either add their SSH key to GitHub or provide a token.
5. **Continue with read-only operations** where possible (e.g., `git clone https://github.com/user/public-repo.git` for public repos).

## Verification

    # Verify git is available
    git --version

    # Verify gh auth (if available)
    gh auth status 2>&1

    # Verify git can reach GitHub
    git ls-remote https://github.com/github/github-services HEAD 2>&1
