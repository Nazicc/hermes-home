---
name: hermes-prerun-script-deploy
description: "Deploy and sync prerun scripts to the Hermes scheduler's ~/.hermes/scripts/ path, accounting for the scheduler's path-traversal allowlist security model. The scheduler's _run_job_script uses Path.resolve() which follows symlinks to their real paths — symlinks will be rejected even if they point inside ~/.hermes/scripts/. Use COPY (make deploy) not symlinks. Also covers post-commit hook automation and new-machine setup via make setup. NOT for: general script deployment unrelated to the Hermes scheduler, or modifying the scheduler's cron configuration directly."
category: general
---

# Hermes Prerun Script Deploy

Deploys and manages prerun scripts for the Hermes Agent cron scheduler. Prerun scripts live at `~/.hermes/scripts/` and are executed before scheduled agent tasks to validate environment or data freshness.

## Scheduler Security Model

The scheduler enforces a **path allowlist** — only scripts under `~/.hermes/scripts/` can be executed. Before running any prerun script, the scheduler:

1. Resolves the script path with `Path.resolve()` (follows symlinks to their real location)
2. Checks that the resolved path is inside `~/.hermes/scripts/`
3. **Blocks execution if the check fails**

**Key insight**: `Path.resolve()` is not a security boundary check — it expands the path to its absolute form, including following symlinks. The scheduler then checks whether that resolved path starts with `~/.hermes/scripts/`.

## Symlink Gotcha

Because the scheduler calls `Path.resolve()`, **symlinks are resolved to their real path** before the allowlist check. A symlink at `~/.hermes/scripts/rss_health_checker.py` → `/Users/can/.hermes/hermes-agent/scripts/rss_health_checker.py` **fails** because the resolved path is outside `~/.hermes/scripts/`.

bash
# DOES NOT WORK — scheduler resolves symlink and sees /Users/can/work/my_script.py
# which is NOT under ~/.hermes/scripts/, so it blocks execution
ln -s /Users/can/work/my_script.py ~/.hermes/scripts/my_script.py

# CORRECT — script lives directly under ~/.hermes/scripts/
cp /Users/can/work/my_script.py ~/.hermes/scripts/my_script.py
chmod +x ~/.hermes/scripts/my_script.py


**Rule**: Prerun scripts must be **copied** (not symlinked) directly into `~/.hermes/scripts/`.

## Deployment Strategy

Do NOT use `ln -s`. Use `make deploy` to **copy** files:

bash
make deploy


The Makefile's deploy target copies prerun scripts from the repo into `~/.hermes/scripts/`, bypassing the symlink path-traversal issue.

## Adding a New Prerun Script

1. **Develop**: Write your prerun script in the repo (e.g., `scripts/my_checker.py`)
2. **Test locally**: `python3 scripts/my_checker.py`
3. **Deploy**: `make deploy`
4. **Register**: Add to the scheduler's cron config:
   python
   "pre_run_scripts": {
       "health_check": {
           "path": "~/.hermes/scripts/rss_health_checker.py",
           "trigger_before": ["feed_sync"],
           "timeout": 60
       }
   }
   
5. **Validate**:
   bash
   # Test the script directly
   ~/.hermes/scripts/rss_health_checker.py
   
   # Check cron is registered
   crontab -l
   
   # Manually trigger the scheduler job
   cd ~/.hermes/hermes-agent && python -m hermes.scheduler run --job feed_sync
   
6. **Commit and push** — post-commit hook auto-deploys on push

## Git Hooks

Git hooks are **local-only** (`.git/hooks/` is in `.gitignore`). Templates live in `scripts/git-hooks/`.

### pre-commit Hook (Secret Scanner)

Scans staged files for leaked secrets (API keys, tokens, passwords) and blocks the commit if found. Template: `scripts/git-hooks/pre-commit`.

**Important**: The pre-commit hook's own template files must be excluded from scanning. The skip pattern `scripts/git-hooks/|Makefile|\.md$` handles this to avoid false positives when updating the hook itself.

**⚠️ Shell quoting gotcha**: The hook uses `grep -E` with a pattern variable (`SCAN_PATTERN='...'`). **Do not** use double quotes for patterns containing `|` — it causes the shell to interpret the pipe as a command separator.

### post-commit Hook (Auto-deploy)

Runs `make deploy` automatically after each commit, keeping `~/.hermes/scripts/` in sync with the repo. Template: `scripts/git-hooks/post-commit`.

## Hook Setup on New Machines

After cloning the repo, restore hooks with:

bash
make setup


This runs `make deploy` and copies both hook templates into `.git/hooks/`.

To reinstall hooks manually after pulling:

bash
cp scripts/git-hooks/pre-commit .git/hooks/pre-commit
cp scripts/git-hooks/post-commit .git/hooks/post-commit
chmod +x .git/hooks/pre-commit .git/hooks/post-commit


## Quick Reference

| Path | Purpose |
|------|---------|
| `~/.hermes/scripts/` | Only allowed location for prerun scripts |
| `scripts/` | Development / template location in repo |
| `.git/hooks/pre-commit` | Active pre-commit hook |
| `.git/hooks/post-commit` | Active post-commit hook |
| `scripts/git-hooks/` | Hook templates (version-controlled) |
