---
name: hermes-agent-git-workflow
description: "Safe git operations for hermes-agent skill development. Covers staged-file safety, destructive command guards, nested repo awareness, write-to-commit patterns, and recovery from accidents."
category: general
---

# Git Workflow for Hermes Skill Development

Safe, repeatable workflow for creating, editing, and committing skill files in the hermes repository. Follow this workflow to avoid data loss from destructive git operations.

## Why This Works

**Concept 1: Pre-destruction checks eliminate the most common data-loss scenarios.** Three out of four accidental `reset --hard` disasters at Hermes happen because the developer didn't check for staged-but-uncommitted files or didn't realize they were in a nested repo. By making checks mandatory, this workflow prevents the root cause before any damage can occur.

**Concept 2: The `execute_code`-with-`os.makedirs` pattern guarantees writes succeed.** `write_file` in Hermes silently fails (returns success without creating the file) when the parent directory doesn't exist. Python's `open()` with explicit `os.makedirs()` raises a clear exception on failure, making the problem immediately visible and debuggable.

**Concept 3: Commit-immediately discipline creates a reflog safety net.** Every commit adds a reflog entry. If you accidentally run `reset --hard` later, the reflog preserves the commit hash, enabling recovery via `git branch recovery-branch <hash>`. The longer the gap between staging and committing, the more work is at risk.

## Pre-Destruction Checks (MANDATORY)

Before running any destructive git command (`reset --hard`, `rebase -i`, `checkout --force`, `clean -fd`), execute ALL of the following:

```bash
# 1. Check working directory — unstaged changes will be LOST
git status

# 2. Check staged files — staged changes will ALSO be LOST under reset --hard
git diff --cached --name-only

# 3. Check staged-but-not-committed files in particular
# These look "safe" in the index but will be wiped by reset --hard
# If any exist, commit them FIRST

# 4. Check reflog for recent HEAD movements
git reflog -10

# 5. Check stash list
git stash list
```

## Staged Files Are NOT Safe From reset --hard

**Critical**: `git reset --hard` moves HEAD AND resets the working tree AND resets the staging area. Any file staged with `git add` but not yet committed will be DELETED from the working tree.

Symptoms of this failure:
- You created a skill with skill_manage, it was staged, but not committed
- You ran `git reset --hard` thinking you were cleaning up
- The skill file is gone from the working tree
- `git status` shows a clean working directory but the file is missing

## Safe File Operations

**Preferred method: use `execute_code` with Python's `open()`**.

```python
import os

# Ensure parent directory exists
skill_dir = os.path.expanduser("~/.hermes/skills/hermes-agent/<skill-name>")
os.makedirs(skill_dir, exist_ok=True)

# Write the skill file
skill_path = os.path.join(skill_dir, "SKILL.md")
with open(skill_path, "w") as f:
    f.write("# Skill content here\n")
```

**Why `execute_code` instead of `write_file`?**

`write_file` silently fails — returning success without creating the file — when the parent directory does not exist. Python's `open()` creates parent directories and raises a clear exception on failure.

**Always verify** the file was written before proceeding:

```python
import os
assert os.path.exists(skill_path), f"File not created: {skill_path}"
print(f"Verified: {skill_path}")
```

## Immediate Commit After Skill Creation

After creating or majorly updating a skill, commit immediately:

```bash
git add skills/hermes-agent/<skill-name>/SKILL.md
git commit -m "feat(skills): add <skill-name> — brief description"
```

**Rule: commit before staging, not after staging**. The safest pattern is to write the file, then immediately commit it.

Do NOT leave skill files staged but uncommitted. "I'll commit after I verify it works" leads to losing the file under a stray reset.

## Staging Safety and Unstaging

If you accidentally stage a file and need to unstage it, use:

```bash
git reset HEAD -- <path>
```

This removes the file from the staging area without modifying the working directory or losing any content.

| Command | Staging area | Working directory | Risk |
|---|---|---|---|
| `git reset HEAD -- <path>` | ✓ Removed | ✓ Intact | Safe |
| `git reset --soft` | ✓ Reset | ✓ Intact | Safe |
| `git reset --hard` | ✗ Wiped | ✗ Wiped | **Destructive** |
| `git checkout -- <path>` | ✓ Intact | ✗ Overwritten | Overwrites uncommitted work |

**Never use `git reset --hard`** to unstage files. It deletes all staged and unstaged changes permanently.

## Stashing Changes

**Before running `git stash`, check the scope of what will be stashed.**

```bash
git stash list
git status   # Shows all files that would be stashed
```

In the hermes repository, there may be many untracked or modified files outside the skill you're working on. Stashing everything creates a bloated stash entry.

**To stash only specific files:**

```bash
git stash push -m "wip: ctf-master skill" -- skills/hermes-agent/hermes-ctf-master/
```

**Drop stashes promptly** after pushing to avoid confusion about which stash corresponds to which work.

## Nested Repo Awareness

The hermes agent may have multiple git repos inside `~/.hermes` at the same time (e.g., ctf-skills, ctf-wiki, awesome-ctf cloned as subdirectories). Before running git commands:

```bash
# Confirm you are in the intended repo
pwd && git rev-parse --show-toplevel

# If cloning repos for exploration, clone them OUTSIDE ~/.hermes
# to avoid git-context confusion and accidental resets
```

Common mistake: running `git reset --hard` in `~/.hermes` when you meant to run it in a subdirectory repo. This will wipe staged files in `~/.hermes` itself.

## Recovery Procedures

### After accidental reset --hard

```bash
# Find the commit hash before the reset
git reflog
# Output looks like:
# abc1234 HEAD@{0}: reset: moving to HEAD~1
# def5678 HEAD@{1}: commit: feat: add my skill
#
# Restore by creating a new branch at the lost commit:
git branch recovery-branch <commit-hash>

# Or directly checkout the lost commit:
git checkout <commit-hash>
```

### Recovering from a cluttered stash

```bash
# View stash list with context
git stash list

# Show files in a specific stash entry
git stash show -p stash@{N}

# Apply only specific files from a stash
# (use git checkout to restore individual files rather than applying whole stash)

# Drop a single stash entry
git stash drop stash@{N}
```

## Remote Operations

**Primary remote for skill pushes: `home`**

```bash
git remote -v
# home   git@github.com:user/hermes.git (fetch)
# origin git@github.com:other/repo.git (fetch)

# Push to home:
git push home main
```

The `origin` remote may contain unrelated force-pushed history. Always confirm the correct remote before pushing.

Before force-pushing:

```bash
git fetch origin
git log origin/main..HEAD  # review unpushed commits
```

Avoid `git push --force` on main branches. Use `git push --force-with-lease` as a safer alternative.

## Examples

**Good:** You create a new skill directory. Instead of `write_file` (which may silently fail), you use Python `open()` with `os.makedirs(exist_ok=True)`. The file is created, verified with `os.path.exists()`, and committed immediately. No staged-but-uncommitted file is left behind.

**Good:** Before a `git reset --hard`, you run `git status` and discover a staged skill file you forgot to commit. You commit it first, then proceed with the reset. The staged file is preserved in the commit history and recoverable via reflog.

**Good:** You need to stash work on a skill while switching branches. Instead of `git stash` (which stashes everything), you use `git stash push -m "wip: skill-x" -- skills/hermes-agent/skill-x/`. Other modified files in the repo remain untouched and trackable.

**Bad:** You run `git reset --hard` to clean up your working tree, forgetting that you had staged `my-new-skill/SKILL.md` with `git add` but not committed it. The file is gone from both the working tree and the index. `git status` reports a clean directory, and the work is lost permanently (unless recovered from reflog if another commit exists nearby).

## Anti-Patterns

**Anti-Pattern 1: Using `git reset --hard` to unstage a file.** The command is designed to wipe the working tree AND staging area. Using it for unstaging is like using a sledgehammer to remove a thumbtack — it works, but at enormous cost. Use `git reset HEAD -- <path>` instead.

**Anti-Pattern 2: Leaving skill files staged but uncommitted.** The pattern "I'll commit after I verify it works" is the single most common cause of skill file loss. A stray `reset --hard` or branch switch destroys the file before you ever hit commit. Always commit immediately after `git add`.

**Anti-Pattern 3: Running git commands without checking `pwd` first.** When `~/.hermes` contains cloned sub-repos (ctf-skills, ctf-wiki, etc.), running `git reset --hard` in the wrong directory can wipe files in a completely different repository. Always run `git rev-parse --show-toplevel` first.

**Anti-Pattern 4: Using `write_file` without verifying the file was created.** `write_file` returns success even if it couldn't create the file (e.g., parent directory missing). Always follow with `os.path.exists()` or an assertion to confirm the file actually exists on disk.

## When NOT to Use

- **Non-hermes git repositories** — This skill is tailored to the hermes-agent skill development workflow. For generic git operations in other projects, use standard git workflows or team-specific conventions.
- **Single-user projects with no staging discipline** — If you never stage files before committing (you use `git commit -am` exclusively), the staged-file safety concerns don't apply. However, the write verification patterns still hold.
- **CI/CD or automated pipelines** — These run in ephemeral environments and rarely deal with hermes skill files. Use platform-specific CI/CD skills for pipeline git operations.
- **Projects using a different VCS (Mercurial, SVN, Perforce)** — The commands and concepts are VCS-specific. Adapt the safety principles (check before destroy, commit early, verify writes) to the target system.

## Cross-References

- **hermes-agent-diagnostics** (skills/hermes-agent-diagnostics/SKILL.md) — Broader hermes-agent runtime diagnostics including provider detection and tool loading issues.
- **hermes-git-nested-repo** (skills/hermes-git-nested-repo/SKILL.md) — Deep dive on nested git repo awareness and context-switching between repos in the hermes workspace.
- **hermes-agent-daily-maintenance** (skills/hermes-agent-daily-maintenance/SKILL.md) — Day-to-day operational commands for running, restarting, and monitoring hermes-agent processes.
