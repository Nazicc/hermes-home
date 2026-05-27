---
name: skill-workflow-memory-management
description: "Use when building a multi-step skill installation, audit, or bulk-update workflow, or when the agent's own accumulated context (memory entries, skill content, tool results) risks exceeding available token/character limits. NOT for general user conversation summarization — use context-compression for that instead."
category: general
---

---
name: skill-workflow-memory-management
description: Use when executing multi-step skill management tasks (install, audit, update, validate multiple skills) where the agent's own accumulated context may overflow. NOT for compressing user conversation — use context-compression for that.
---

# Skill Workflow Memory Management

When running multi-step skill workflows (e.g., batch installs, audits, bulk validation), the agent's own context grows with each step (skill content, tool outputs, git diffs, memory entries). **Proactively manage your own context**, not just the user's.

## Proactive Checkpoints

Before starting a batch workflow, check current memory usage:

What is my current memory usage? How many entries and approximately how many characters?


If already at >1,500 chars, **trim before starting**, not after overflow.

## Mid-Workflow Triggers

Check your context size at these natural breakpoints:
- After installing 3+ skills in a batch
- After running `git diff` or `git status` on multiple files
- After loading 2+ `skill_view` calls
- Before a `git commit` + `git push` sequence
- After `memory` tool shows "full" or near-limit

**Checkpoint question**: "Am I accumulating too much context for this workflow? Should I snapshot memory, commit, then continue?"

## Overflow Recovery

If you hit an overflow (tool returns 422 or "would put memory at X/Y chars"):

1. **Do NOT restart the whole session** — restart loses all accumulated knowledge
2. **Delete the memory snapshot file** to get a clean slate for memory:
   bash
   rm ~/.hermes/.skills_prompt_snapshot.json
   
   Then re-add only the most critical entries (2-3 lines each).
3. **Commit your work in progress** with a partial commit message before trimming
4. **Resume from the last git commit**, not from scratch

## Memory Entry Strategy for Multi-Step Workflows

Keep memory entries for skill workflows **under 200 characters each**. Use abbreviations:


# Good (80 chars)
skills: hermes=~/.hermes/, skills=~/.hermes/skills/skills/{name}/SKILL.md; snapshot=~/.hermes/.skills_prompt_snapshot.json

# Bad (500+ chars — will itself cause overflow)
skills installation path (2026-04-24): hermes home = ~/.hermes/... [long explanation]


## Batch Skill Operations

For batch operations (N > 3 skills), prefer:

1. **Single Python script** to do fetch + format check + patch + write in one pass, then `terminal` invoke it once
2. **Git add all at end** — do NOT `git add` after each file, accumulate then commit once
3. **One `skill_view` call per skill** — do NOT pre-load all batch-2 skills simultaneously
4. **One memory update at very end** — not after each sub-step

## Git Checkpoint Discipline

Commit after each logical phase, even if incomplete:
bash
git add skills/skill-a/ skills/skill-b/ && git commit -m "partial: install batch"


This way if memory overflows mid-workflow, you can `git log --oneline`, find the last good commit, and resume from there — no work lost.

