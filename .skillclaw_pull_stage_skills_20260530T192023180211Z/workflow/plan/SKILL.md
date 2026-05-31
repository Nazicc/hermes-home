---
name: plan
description: "Plan mode for Hermes Agent — inspect context, write a markdown plan into the workspace's `.hermes/plans/` directory, and do NOT execute the work. User must approve the plan before execution begins. Use when: user asks for a plan, task is complex/multi-step, architectural decisions are needed, changes are risky, or when uncertain about the correct approach. NOT for: simple one-liner tasks, urgent hotfixes, or when user explicitly asks to just do it."
category: workflow
---

## When to Use Plan Mode

**Activate plan mode when ANY of these apply:**

- Task has 3 or more distinct steps
- Task involves modifying more than 2 files or multiple subsystems
- Task could have irreversible consequences (deletes, migrations, deployments)
- Task involves external services, APIs, or network calls
- Requirements are ambiguous or incomplete
- Task touches security, authentication, or infrastructure
- You are uncertain about the correct approach
- User uses phrases: "plan", "make a plan", "figure out a plan", "design", "how should we", "what's the best approach", "what would you do", "plan this out", "outline", "how would you"

**Skip plan mode when:**
- Task is a single tool call (read a file, run a command)
- Simple question with a known answer
- Well-understood routine (e.g., `grep`, `ls`, `cat`)
- Single-file edits, one-liners, or trivially reversible changes
- User explicitly says "just do it" or "don't ask, just go"
- Reading/analysis tasks that don't modify state
- Direct follow-up to a just-approved plan
- Already have a confirmed spec (use `spec-driven-development` instead)

## Plan Mode Protocol

### Step 1: Inspect Context

Before writing the plan:
1. Read relevant skill files to understand available tools/patterns
2. Check the workspace for existing code, configs, tests
3. Identify dependencies and constraints
4. Understand the current state of the codebase/project
5. If a skill file or read operation returns **empty content or an error**, do NOT proceed silently. Flag the issue and abort until resolved.
6. Do NOT continue if context inspection reveals missing critical information

### Step 2: Check Existing Plans

`ls "$WORKSPACE/.hermes/plans/"` to avoid duplicate plans.

If an existing plan matches the current task:
- Read it first
- Compare against current task
- Either: resume execution (if still valid), update it, or write a new plan

### Step 3: Write the Plan

Plans are written to the workspace's `.hermes/plans/` directory:

bash
mkdir -p "$WORKSPACE/.hermes/plans/"


If the workspace root is not writable, fall back to `~/.hermes/plans/`.

**Naming Convention**: `YYYY-MM-DD-<slug>.md`


.hermes/plans/
├── 2026-04-24-feature-x-auth.md   # ✓ Good: date + descriptive slug
├── 2026-04-24-migration-v2-*.md    # ✓ Good: include version/scope
├── today-debug-*.md                 # ✗ Avoid: vague names
└── plan.md                         # ✗ Avoid: generic names


- Include the date for temporal ordering
- Use a descriptive slug (kebab-case, max 50 chars)
- Avoid generic names like "plan.md" or "todo.md"

### Step 4: Deliver Plan

Write the plan file, then present a summary to the user:

> **Plan Summary**
>
> This plan has **N steps**:
> 1. <Step 1 summary>
> 2. <Step 2 summary>
> ...
>
> Estimated complexity: <low/medium/high>
>
> Say **"go"** to approve or **"stop"** to cancel.

**Do NOT execute any work steps until the user approves the plan.**

### Step 5: After Approval

Execute steps sequentially. After each step:
- Verify the step produced expected output
- If a step fails, stop and report before continuing
- Update the plan markdown to reflect completed/failed steps

## Plan Structure

markdown
# Plan: <Task Title>

**Date**: YYYY-MM-DD  
**Status**: draft → under-review → approved → in-progress → done

## Context
What we know about the current state

## Goals
What success looks like

## Steps
1. [ ] <Step description> — file path / command
2. [ ] <Step description> — file path / command
   - Note: any gotchas or things to watch for

## Verification
How to confirm the plan worked

## Risks / Tradeoffs
Known risks and alternatives considered

## Rollback Plan
How to undo if something goes wrong.

## User Approval
- [ ] Approved — proceed with execution
- [ ] Modified — user will provide updated direction


### Step Template

For each step, include:

| Field | Required | Example |
|-------|----------|---------|
| **File(s)** | Yes | `src/auth.py`, `migrations/002.sql` |
| **What** | Yes | "Add JWT middleware to /api/auth route" |
| **Verify** | Yes | "curl /api/auth/login returns 200 + token" |
| **Risk** | If destructive | "Data loss if migration fails" |
| **Approx. time** | Optional | "~10 minutes" |

## Approval Flow

| User response | Action |
|---|---|
| "go" / "yes" / "do it" / "proceed" | Execute the plan |
| "stop" / "cancel" / "never mind" | Abandon, ask for feedback |
| "change X" / "instead of Y, do Z" | Update plan, re-present |

## Handling Revisions

If user rejects or modifies the plan:
1. Update the plan file with the revised approach
2. Re-present with changes highlighted
3. Wait again for approval

If during execution something unexpected happens:
1. Stop immediately
2. Write an updated plan to handle the new situation
3. Present to user for approval before continuing

Do not silently change scope or add work not in the approved plan.

## Common Pitfalls

### Silent Failure
**Problem**: read_file returns empty content but agent proceeds anyway.
**Fix**: Always check that file reads returned actual content. Empty ≠ "file doesn't exist" — it could mean a path error or permission issue. Treat empty as an error condition.

### Skipping Verification
**Problem**: User approves plan, agent executes everything at once, only then discovers something went wrong.
**Fix**: Execute steps one at a time. Verify after each step. Update the plan file as you go.

## Quality Checklist

Before presenting a plan, verify:

- [ ] Goal is clear and achievable
- [ ] All steps are in correct order
- [ ] Every step has a specific file path or command
- [ ] Every step has expected outcome and verification criteria
- [ ] No steps are missing prerequisites
- [ ] File paths are accurate (verified they exist or are new)
- [ ] Rollback is defined for each destructive change
- [ ] Risks are identified with mitigations
- [ ] Plan is scoped to the user's request (not over-engineered)
- [ ] Step names are clear and actionable

## Anti-Patterns

**Never skip the plan** even if you're confident:
- Multi-step deployments
- Database migrations
- Any `DROP`, `DELETE`, or `rm -rf` commands
- Changes to running services

**Never execute without approval** when plan mode is active.

**DO NOT:**
- Execute steps while writing the plan
- Write vague plans ("improve the code", "fix the bug")
- Plan 20 steps for a 3-step task — keep scope tight
- Skip step verification
- Skip rollback plan for risky changes
- Assume approval — wait for explicit confirmation
- Write plans with only 1 step (that's not a plan, just execute)
- Use vague criteria like "test it" — be specific: "`pytest tests/ -v` passes with 0 failures"
- Write vague steps like "update the config" — be specific: "edit `config.yaml` line 12: change `timeout: 30` to `timeout: 60`"
- Write a plan longer than 500 lines — if it's that complex, the task probably needs to be split

**DO:**
- Be specific about file paths and expected outcomes
- Include verification for each step
- Think about what could go wrong
- Write in present tense ("Create", not "Creates")
- Keep plans scoped to a single session; break huge tasks into sub-plans

## Integration with Other Skills

- `spec-driven-development` — Write SPEC.md first, then use this skill to plan implementation
- `writing-plans` — Detailed guidance on breaking down complex tasks into steps
- `systematic-debugging` — Use when planning a fix for a bug
- `incremental-implementation` — For large tasks, plan each increment separately

## Token-Saving Rules

- Write the plan, not an essay. Aim for < 300 words
- Skip verbose background research in the plan itself
- If you need to research something before writing a good plan, do ONE tool call, then write the plan. Don't loop
- Use the plan file, not a multi-turn conversation, to communicate the plan

## Quick Reference

| Scenario | Action |
|----------|--------|
| Task = 1-2 simple steps | Execute directly |
| Task = 3+ steps or risky | Write plan, wait for approval |
| Unsure about approach | Write plan, ask for guidance |
| User says "just do it" | Execute without planning |
| Plan changes mid-execution | Stop, replan, re-approve |
| Existing plan found | Read it, compare, resume or revise |
| User says "write a spec" | Use spec-driven-development first |
| read_file returns empty | Flag error, abort plan until resolved |
