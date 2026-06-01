---
name: writing-plans
description: "Creates comprehensive implementation plans with bite-sized tasks, exact file paths, and complete code examples. Use when you have a spec or requirements for a multi-step task and need to break it down into executable steps."
---

## Purpose

Use this skill when you need to break down a multi-step task into a structured, executable plan. The user has a goal but needs it decomposed into independent, verifiable steps with exact file paths, code snippets, and verification commands. This skill transforms ambiguous requirements into actionable checklists.

**Do NOT use** for debugging (use systematic-debugging), simple one-step tasks (just do it), agent self-evolution planning (use skills-evolution-from-research), or when the user explicitly says "just do it."

## Why This Works

Plans fail when steps are too vague, dependencies are invisible, or verification is deferred until the end. This skill prevents all three failure modes:

**Inversion of Control (IoC).** The plan puts decision points first — file paths, architecture choices, and API contracts — so the agent doesn't have to invent structure mid-execution. Each step is a self-contained unit with a defined input, action, and verification command. This eliminates "implement auth" as a step and replaces it with "create src/services/auth.py with login() and logout() using JWT."

**Phase-based gating.** By organizing steps into independently verifiable phases (Foundation, Core Feature, Integration, Polish), the plan creates natural rollback points. If Phase 1 fails, you don't waste time on Phase 2. Each phase has its own verification check.

**Verification-before-execution discipline.** Every step includes a verification command — not as an afterthought, but as a requirement. This turns each step from "do X" into "do X, then confirm X works."

**Reusable templates.** Instead of reinventing the wheel for every database migration or API endpoint, the skill provides reusable templates. This cuts planning time by 40-60% for recurring task types while ensuring nothing is forgotten.

## Context

**Complexity Scale

| Rating | Time | Scope |
|--------|------|-------|
| XS | <10 min | Single file, no new deps |
| S | 10-30 min | 1-2 files, known stack |
| M | 30-90 min | 3-5 files, some unknowns |
| L | 90+ min | Many files, research needed |

For complexity M or L, recommend entering plan mode.
**
**Plan Directory

All plans go in `.hermes/plans/`. Filename: `YYYY-MM-DD-short-slug.md`

## Architecture
**
**Plan Structure (8 sections)
**
1. **Overview** — One-paragraph summary of what and why
2. **Context** — Current state, constraints, related files
3. **High-Level Approach** — Key architectural decisions
4. **Prerequisites** — Environment, dependencies, credentials
5. **Task List by Phase** — The actual steps, organized into phases
6. **File Inventory** — Table of files to create/modify/delete
7. **Verification Checklist** — End-to-end checks
8. **Rollback** — How to undo

**Phase Naming Convention
**
- **Foundation** — project scaffolding, deps, config
- **Core Feature** — main implementation
- **Integration** — connecting components
- **Testing** — unit and integration tests
- **Polish** — edge cases, error handling, docs

Each phase must be independently verifiable.

**Task Ordering Rules

1. Prerequisites and scaffolding first
2. Core logic before integration
3. Tests before edge cases
4. Integration last
**
**Step Writing Principles
**
- **Bite-sized:** Each step completable in <10-20 minutes, independently verifiable, atomic
- **Exact File Paths:** Full relative path from workspace root
- **Verification Per Step:** Include a verification command after each step
- **Code Examples:** Include complete code when writing new logic

**Token-Saving Strategies

1. Once a pattern is established, omit prefixes for subsequent steps
2. Reference existing patterns instead of repeating code
3. Skip obvious steps
4. Use tables for multi-item steps
**
**Handling Ambiguous Requirements

1. State assumptions explicitly in the Context section
2. Ask the user to clarify before proceeding
3. Provide options with tradeoffs
**
**Hermes Plan Mode Integration

If plan skill is active:
1. Write the plan to `.hermes/plans/`
2. Do NOT execute any steps
3. Present the plan to the user
4. Wait for explicit approval
5. Only then execute
**
**Interaction Pattern

After writing the plan:
1. Summarize in 3-5 sentences
2. State total steps and complexity/risk level
3. Ask for explicit approval before executing
4. If user approves partially, execute those phases and stop

## Examples
**
**Good:** Breaking down a multi-file feature into phased steps

User asks: "Add OAuth login with Google and GitHub providers"

```
**Phase 1: Foundation (2 tasks)
- [ ] 1. Add OAuth dependencies to requirements.txt
- [ ] 2. Create src/settings/oauth.py with provider config classes
**
**Phase 2: Auth Providers (3 tasks)
- [ ] 3. Add Google OAuth handler in src/auth/google.py
- [ ] 4. Add GitHub OAuth handler in src/auth/github.py
- [ ] 5. Register callback URLs in src/auth/urls.py
```**
**Good:** Every step has an exact file path, action verb, and verification path. Phases are independently testable.

---

**Bad:** Writing a vague single-paragraph overview instead of structured steps

User asks: "Need to add user login"

```
Create a login system with Google support. Add the necessary dependencies. Update the auth module. Don't forget tests.
```
**Bad:** No file paths, no step decomposition, no verification plan. "Update the auth module" is not actionable.

---

**Good:** Including verification commands in every step

```
**Step 4: Create JWT token utility**
**File(s):** src/auth/jwt.py
**What:** Implement create_token(user_id) and verify_token(token).

Verification:
python -c "from src.auth.jwt import create_token, verify_token; t = create_token(1); print(verify_token(t)['user_id'])"
```
**Good:** The verification command immediately confirms the implementation produces correct output.

---

**Bad:** Trusting without verification

```
**Step 4: Create JWT token utility**
**File(s):** src/auth/jwt.py
```
**Bad:** No way to confirm the functions work. If the JWT secret is missing or the algorithm is wrong, you discover it only during integration testing.

---

**Good:** Creating rollback-aware plans for database migrations

```
**Phase 2: Schema Migration (1 task)
- [ ] 3. Create migrations/004_add_user_preferences.sql

Verification:
psql -c "SELECT column_name FROM information_schema.columns WHERE table_name='user_preferences'"

Rollback:
DROP TABLE IF EXISTS user_preferences;
```**
**Good:** Schema is reversible. Verification confirms the table structure.

---

**Bad:** Migration without rollback

```
- [ ] 3. Run migration to add user_preferences table
```
**Bad:** No SQL shown, no verification, no rollback. If the migration errors out, the database is in undefined state.

---

**Bad:** Using plans for simple tasks

User asks: "Change the port in config from 3000 to 8080"

```
**Plan to update config port**
**Overview:** Change the port number in config.yaml
**Steps:**
1. Open config.yaml
2. Find the port: 3000 line
3. Change to port: 8080
```
**Bad:** This is a single-line edit. No plan needed.

---

**Good:** Documenting assumptions and unknowns

```
## Assumptions
- [x] PostgreSQL 14+ running on localhost:5432
- [ ] The users table has a unique email column
- [ ] Rate limiting middleware exists in src/middleware/rate_limit.py

## Open Questions
- Should tokens expire or be long-lived?
- What permissions does the MVP need?
```
**Good:** Assumptions are explicit checkboxes. Unknowns are flagged for the user.

## When NOT to Use

- **Debugging** — Use systematic-debugging to investigate first, then plan the fix
- **Simple one-step tasks** — A single file edit or one command doesn't need a plan
- **Emergency fixes** — A production outage needs immediate action, not structured planning
- **When the user says "just execute"** — Respect their preference for speed
- **Agent self-evolution planning** — Use skills-evolution-from-research
- **Existing detailed specs** — Use spec-driven-development instead
- **Reviewing an existing plan** — Use plan skill to load and review

## Cross-References

- **systematic-debugging** (skills/systematic-debugging/SKILL.md) — Use this first when investigating bugs. Analyze before planning fixes.
- **spec-driven-development** (skills/spec-driven-development/SKILL.md) — Create specs before writing plans. This skill consumes specs as input.
- **test-driven-development** (skills/test-driven-development/SKILL.md) — Plans should include test-first steps. TDD provides per-step testing discipline.
- **incremental-implementation** (skills/incremental-implementation/SKILL.md) — For large plans, use checkpoint comments for partial commits.
- **plan** (skills/plan/SKILL.md) — Plan mode for user-approval gating.
- **context-engineering** (skills/context-engineering/SKILL.md) — Set up clean context before writing plans.
- **deerflow-commander** (skills/deerflow-commander/SKILL.md) — Delegate large research-intensive plans to DeerFlow for deeper analysis.
