---
name: systematic-debugging
description: "Use when encountering any bug, test failure, or unexpected behavior. 4-phase root cause investigation. CRITICAL: No fixes without understanding the problem first. Covers shell scripts, Python, and Hermes system debugging with verified file persistence workarounds."
---

## Purpose

Activate this skill when any bug, test failure, or unexpected behavior appears. The 4-phase scientific method (Observe, Hypothesize, Test, Iterate) forces root-cause investigation before any fix is attempted.

**Do NOT use** for simple syntax errors you already understand (just fix it), feature implementation (use spec-driven-development instead), or when the user explicitly says "try X" (they want a specific hypothesis tested). Do use it whenever the root cause is unclear, the error is intermittent, or you find yourself guessing.

## Why This Works

**Premature fixes are the #1 source of technical debt in AI-assisted coding.** When an agent has a plausible theory 10 seconds into reading a stack trace, the temptation is to fix immediately — but plausible theories are wrong 60% of the time. The 4-phase structure is deliberately slow: it forces you to collect facts (Phase 1) before forming theories (Phase 2). This replaces "I think it's X, let me try" with "I know it's X because the evidence says so."

**Falsifiability prevents confirmation bias.** Every hypothesis must be stated as a testable claim. "The database connection failed" is a hypothesis; "PORT=5432 is unreachable from this subnet" is a testable claim. The difference prevents you from fixing a port issue when the actual problem is a firewall rule.

**One-variable-at-a-time testing.** Multiple changes simultaneously means you never know which one fixed the bug. The skill enforces single-variable changes — fix one thing, test, then move on.

**Shell awareness reduces silent failures.** `set -e` in shell scripts causes silent exits. The skill's shell-specific guidance catches this class of bug before you waste 20 minutes looking elsewhere.

## Phase 1: Observe

Collect facts, not assumptions. Do NOT guess, do NOT fix.

**What to collect:**
- The exact error message or unexpected output
- The command/context that triggered it
- Relevant log entries (stderr, stdout, application logs)
- What changed recently (dependency updates, config changes, new commits)
- Exit codes and stack traces
- What was the last working state?

**Commands:**

```
# Check recent git changes
git log --oneline -5
git diff HEAD~1

# For shell scripts: use bash -x for maximum verbosity
bash -x script.sh 2>&1 | grep -v "^++"

# Check exit codes explicitly after critical commands
cmd; echo "exit: $?"
```

**Shell-specific checks:**
- Check file permissions, symlinks, path variables
- Check `set -e` behavior — script may exit early without error message
- CRITICAL anti-pattern: `set -e` combined with `[ $? -eq 0 ]` always exits because `$?` is the exit code of `[`, which is always 0 or 1

**Output of Phase 1:** A concise list of facts (not interpretations).

## Phase 2: Hypothesize

State the root cause as a testable claim. Each hypothesis must be falsifiable.

**Rules:**
- List ALL plausible hypotheses before choosing one
- Prefer the simplest explanation that fits all facts
- Distinguish symptoms from root causes
- Never say "I'll try X and see" — first understand why X would work

**Hypothesis template:**

```
H1: <cause> → <effect>
  Evidence supporting: ...
  Evidence against: ...

H2: <alternative cause> → <effect>
  Evidence supporting: ...
  Evidence against: ...
```

**Common root causes (check in order):**
1. Environment mismatch (wrong port, missing env var, network)
2. API/contract change (endpoint, payload schema, auth)
3. Race condition or ordering dependency
4. Missing resource or dependency not installed
5. Configuration error (typo, wrong path)
6. Logic error in the code itself

## Phase 3: Test

Verify the hypothesis with a targeted test. One variable at a time.

```
# Test environment state
echo $PORT && curl http://127.0.0.1:$PORT/healthz

# Check if resource exists
ls -la ~/.hermes/<path>

# Minimal reproduction
python3 -c "import <module>; <module>.<func>()"

# Shell: syntax check before running
bash -n script.sh
```

**Principles:**
- Test the specific hypothesis, not multiple things
- If the test passes, hypothesis is likely correct — move to Fix
- If the test fails, hypothesis is wrong — return to Phase 2
- Run with dry-run flags if available

## Phase 4: Iterate

Refine based on test results. Once root cause is confirmed, fix it and verify.

**Fixing rules:**
- Fix the root cause, not the symptom
- Write a regression test to prevent recurrence
- For complex fixes, use incremental-implementation skill
- After fix, re-run the original failing case, then run full test suite

**Verification checklist:**
- [ ] Original error is gone
- [ ] Related functionality still works
- [ ] Regression test passes
- [ ] No new errors in logs

**If hypothesis was wrong:** Return to Phase 2 with new evidence.

## Examples

**Good:** Following the full 4-phase process before making a change

A user reports: "The login endpoint returns 500 error"

```
Phase 1: Observe
- Endpoint: POST /api/login returns HTTP 500
- Logs show: "DatabaseError: relation 'users' does not exist"
- Migration log: migration 004 was rolled back yesterday

Phase 2: Hypothesize
H1: Migration 004 that created the users table was rolled back → table doesn't exist
  Evidence: rollback timestamp matches outage start
H2: Database connection pool exhausted → connection refused
  Evidence against: other endpoints work fine

Phase 3: Test
psql -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='users')"
→ returns false

Phase 4: Fix
Re-run migration 004 and verify table exists
```
**Good:** Facts collected before hypotheses, hypotheses are testable claims, single-variable test confirms.

---

**Bad:** Jumping straight to a fix without understanding

User: "Login endpoint returns 500"

```
The user report shows a 500 error on login.

Let me check if the password hashing library is installed.
pip list | grep bcrypt
```
**Bad:** No observation phase. Starting with a random hypothesis ("password hashing library") with zero evidence. Six other plausible causes are never considered.

---

**Good:** Using single-variable testing for a shell script bug

Script exits at line 42 with no error message. `set -e` is enabled.

```
Phase 1: Observe
- Exit code 1 (from set -e)
- No error output to stderr
- set -e is enabled at line 1
- Line 42 is: output=$(some_command)

Phase 2: Hypothesize
H1: some_command returns non-zero → set -e kills the script
H2: some_command writes to stderr which is redirected

Phase 3: Test
Run the script with bash -x:
bash -x script.sh 2>&1 | tail -20
→ Confirms: "+ some_command" exits with code 1, script stops

Phase 4: Fix
Wrap in: output=$(some_command || true)
```
**Good:** Observes the silent exit, recognizes `set -e` behavior, uses single-variable test (bash -x), applies minimal fix.

---

**Bad:** Ignoring shell-specific behavior

```
Script exits at line 42 with no error. Must be a config issue. Let me check the config file permissions.
```
**Bad:** Ignores `set -e` as a possibility. Checks permissions first — a classic guess, not an observation-driven hypothesis.

---

**Good:** Handling the write_file/patch persistence trap on macOS

After writing a file with write_file that reports success but terminal shows old content:

```
Phase 1: Observe
- write_file(path, content) returns {"written": true}
- read_file(path) shows old content
- terminal: cat path shows old content

Phase 2: Hypothesize
H1: write_file returns cached success without writing
H2: read_file returns cached content

Phase 3: Test
wc -c path  # Compare to expected
→ Byte count doesn't match, confirming H1

Phase 4: Workaround
# Use /tmp + terminal method
/bin/cp -f /tmp/source /real/target/file
wc -c /real/target/file  # Verify with terminal
```
**Good:** Detects the persistence issue, tests with byte count, applies known workaround, verifies with terminal.

---

**Bad:** Trusting tool output without terminal verification

```
write_file("/path/to/file", "new content")
→ Success! Let me proceed.
```
**Bad:** No verification step. On macOS with `cp` aliases, this may silently fail to persist. Always verify with terminal.

## Anti-Patterns

1. **Fix-before-understanding** — Applying a fix before finishing Phase 1 and Phase 2. Creates new bugs from the same root cause. Always observe and hypothesize first.
2. **set-e-and-dollar-question** — Using `[ $? -eq 0 ]` after `set -e`. `$?` captures the exit code of `[`, not the previous command. Use a sentinel variable instead: `result=$?; [ $result -eq 0 ] || exit 1`.
3. **Multi-variable jump** — Changing two things at once and testing both. The fix that worked is unknown. Change one variable, test, then the next.
4. **Silent-failure assumption** — Assuming no error message means no error. Under `set -e`, a command failure kills the script silently.
5. **Blind restart** — Restarting services as a debugging technique. It clears state and loses evidence. Observe first, restart as a targeted test only.
6. **API-stability assumption** — Assuming third-party APIs return the same shape. They change. Check the actual contract in logs or test calls.
7. **Stale-state blindspot** — Assuming cached or environment data is fresh. Scripts read from previous runs, config files are stale, environment variables are wrong. Verify.
8. **macOS-cp-alias trap** — Using bare `cp source dest` on macOS. It's aliased to `cp -i` and hangs on confirmation. Always use `/bin/cp -f`.

## When NOT to Use

- **Syntax errors you understand** — If you see a missing import and know the fix, just fix it
- **Feature implementation** — Use spec-driven-development to plan the new feature
- **When the user says "try X"** — They want a specific hypothesis tested; don't override with the full process
- **Cosmetic issues** — Typos, formatting, and obvious one-line fixes don't need the 4-phase process
- **Code review feedback** — Use requesting-code-review for structural feedback on PRs

## Cross-References

- **writing-plans** (skills/writing-plans/SKILL.md) — After finding the root cause, create a plan for the fix instead of patching blind.
- **test-driven-development** (skills/test-driven-development/SKILL.md) — Write regression tests after fixing. Phase 4 companion.
- **spec-driven-development** (skills/spec-driven-development/SKILL.md) — If the bug reveals missing requirements, create a spec first.
- **incremental-implementation** (skills/incremental-implementation/SKILL.md) — For complex multi-file fixes, use checkpoint comments.
- **context-engineering** (skills/context-engineering/SKILL.md) — When debugging reveals context pollution, reset and re-observe.
- **hermes-agent-diagnostics** (skills/hermes-agent-diagnostics/SKILL.md) — For Hermes system-level issues, start here first.
- **deerflow-commander** (skills/deerflow-commander/SKILL.md) — Delegate deep research on unfamiliar technologies during debugging.
- **Skills quality scorer format** (references/skills-quality-scorer-format.md) — Reference for the skills-quality MCP server format requirements. Use when skill quality scores don't match expectations.
