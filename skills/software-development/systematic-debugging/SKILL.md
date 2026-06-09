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

### 回归测试失败分类法（Regression Failure Triage）
当遇到测试套件批量失败（如 49 跑 27 挂），**不要逐个修**。用四步归类法：

1. **运行全量** — 先跑 `pytest -v test_file.py --tb=short` 获取完整失败清单
2. **读真实接口** — 测试假数据与真实模块接口脱节时，先读模块源码确认正确字段和签名
3. **按根因分组** — 把失败用例归入 3-5 个根因类别（如：A=非法字段、B=缺必需参数、C=模式不匹配、D=上下文判断）。用 count 量化影响："17 cases via A, 7 via B, 3 via C, 1 via D"
4. **每组一个 patch 辐射多个用例** — 修复工厂函数或最上游调用，而非逐一修每个用例
5. **受限工具生效** — 当 `execute_code` 被 blocked（如 cron 安全模式），使用 `patch` 工具做批量替换
6. **Read real interfaces per source group** — After grouping failures, read the actual model/constructor signatures for each group. Compare field-by-field against fixture definitions. For the full workflow, see `references/fixture-model-contract-repair.md`.

### Phase-Gated Verification for Multi-Phase Changes

When a fix or system change spans multiple phases (e.g., Phase A: cleanup → Phase B: infra setup → Phase C: reset), **do not start Phase N+1 until Phase N has been verified independently**. Stacking unverified changes creates cascading failures where a Phase A bug contaminates every subsequent phase's investigation.

**Rules:**
- Define phase gates upfront: for each phase, specify what must be verified before moving on
- Run targeted verification tests on Phase N's specific changes before proceeding
- If Phase N's verification fails, fix it before touching Phase N+1
- Report verification results explicitly: "verified: [tests passed]" or "failed: [reasons]"
- **Never skip verification between phases** — the cost of finding a Phase A bug during Phase C is 10x higher

**Typical verification targets per phase type:**
- **Cleanup phase:** files removed, processes gone, ports freed, cron jobs deleted, script references patched
- **Infrastructure phase:** health endpoints responding, service status OK, config valid, dependencies installed
- **Data phase:** schema intact, stored procedures valid, evolution/stats produced expected output

**Multi-evidence verification:** For critical phase gates (e.g., confirming a decommissioned component is truly gone), verify from multiple independent sources — `ls` for files, `pgrep` for processes, `lsof` for ports, `cronjob list` for jobs, `grep -r` for script references. One source can produce a stale result; two independent sources confirming the same fact cannot.

**Cross-reference:** See `writing-plans` skill's "Phase-based gating" section for planning guidance. This section covers the execution-time gating discipline.

**Fixing rules:**
- Fix the root cause, not the symptom
- Write a regression test to prevent recurrence
- For complex fixes, use incremental-implementation skill
- **MANDATORY: After EVERY fix, run manual regression verification.** Do NOT say "it should work now", "ready to test when you are", "theoretically fixed", or "will work on next schedule tick". Actually invoke the fix (trigger the command, run the test, call the function) and confirm the output is correct. Coverage: at minimum the original failing case + a smoke test of related functionality. If the fix can't be exercised immediately (e.g., scheduled job), trigger it manually (cronjob action='run') and verify the output file.

**Verification checklist (MUST complete all items):**
- [ ] Original error is gone — manually triggered and confirmed
- [ ] Related functionality still works — smoke test passed
- [ ] Regression test passes — test suite run and all passing
- [ ] No new errors in logs — checked after verification
- [ ] User is told actual output/results, not promises

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

2. **Dismissing system verifier warnings without evidence** — When a safety guardrail or verifier (e.g., Hermes file-mutation verifier, permission warnings, validation errors) fires, never say "it's harmless" or "don't worry about it" without proving that claim. The user will rightfully demand evidence. Always:
   - Read the verifier's source code to understand what condition triggered it
   - Check the file system for the referenced paths (confirm existence or non-existence)
   - Verify through an independent mechanism that the intended operation actually succeeded
   - Present concrete evidence (file listings, source code excerpts, test results) not just a claim
   - If a previous turn produced a stale warning, acknowledge it directly and explain why it no longer applies — don't silently ignore
2. **set-e-and-dollar-question** — Using `[ $? -eq 0 ]` after `set -e`. `$?` captures the exit code of `[`, not the previous command. Use a sentinel variable instead: `result=$?; [ $result -eq 0 ] || exit 1`.
3. **Multi-variable jump** — Changing two things at once and testing both. The fix that worked is unknown. Change one variable, test, then the next.
4. **Silent-failure assumption** — Assuming no error message means no error. Under `set -e`, a command failure kills the script silently.
5. **Blind restart** — Restarting services as a debugging technique. It clears state and loses evidence. Observe first, restart as a targeted test only.
6. **API-stability assumption** — Assuming third-party APIs return the same shape. They change. Check the actual contract in logs or test calls.
7. **Stale-state blindspot** — Assuming cached or environment data is fresh. Scripts read from previous runs, config files are stale, environment variables are wrong. Verify.
8. **macOS-cp-alias trap** — Using bare `cp source dest` on macOS. It's aliased to `cp -i` and hangs on confirmation. Always use `/bin/cp -f`.

9. **dict-type-alias-attribute-access** — When a type is declared as `VerifyFinding = dict[str, Any]`, Pyright correctly reports `"code" is unknown on "dict[str, Any]"` when you write `f.code`. This is **not a false positive** — Python dicts don't support attribute access at the type level. Always use subscript access `f["code"]` for dict aliases. See `references/python-dict-type-aliases.md` for diagnosis and bulk-fix workflow.

10. **macOS-symlink-redirection trap** — `cat > symlink` (and any `> symlink` redirection) follows the symlink chain and writes to the **target file**, not replacing the symlink itself. This corrupts real binaries if the symlink chain ends at a system file (e.g., a uv-managed Python binary). **Dangerous pattern:**

11. **Stale-.pyc-bytecode blindspot** — Python's `__pycache__` caches compiled bytecode and masks syntax errors,
    missing imports, and undefined functions introduced by file edits. A test suite that passed 90/90 one minute
    can fail with `0 collected` and `SyntaxError` / `NameError` / `ImportError` the next — **only after the cache
    is invalidated**. The stale cache makes the bugs invisible.

12. **namespace-package-empty-directory** — `python3 -m <package>` fails with *"'<package>' is a package and cannot be directly executed"*. The module directory exists but contains **no Python files** at all (no `__init__.py`, `__main__.py`, or implementation files). Python treats it as a namespace package — a valid importable name with zero code — but can't execute it. The fix is to restore the files from git history rather than creating stubs. See `references/namespace-package-empty-directory.md` for the full diagnosis and recovery recipe.

    **How to detect:**
    - pytest shows `0 collected` with import/syntax errors you didn't see before
    - You made multiple edits to a module and the first test run passed, but a later run fails on something
      that should have been caught earlier
    - Python reports a NameError for a function you *know* is in the file — because the cache holds an older
      version of the module (fewer functions)

    **Root cause:**
    - write_file / patch updates the `.py` source file but the corresponding `.pyc` in `__pycache__/` is not
      automatically invalidated in all cases (macOS HFS+ timestamp quirks, cross-directory imports, nested
      package structure)
    - `rm -rf __pycache__` forces recompilation and reveals the real errors

    **Fix:**
    ```bash
    # Clear ALL __pycache__ dirs in the project (source + tests)
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

    # Then re-run
    python -m pytest test_file.py -v
    ```

    **Prevention:** After every 3+ edits to a source module, or any time you get a suspicious "0 collected",
    clear `__pycache__` before running tests. This prevents a latent-bug cascade where each fix reveals the
    next underlying error.

    **Example from production (anfu-skill sources.py):** Four latent bugs were hidden by stale `.pyc`:
    - Missing `_mock_cnvd_items` function (NameError on import)
    - Escaped triple-quotes in docstring (SyntaxError)
    - Over-escaped backslashes in regex (SyntaxError)
    - Missing `_real_cnvd_items` function (NameError at module init)
    All four surfaced in sequence after one `find . -name __pycache__ -exec rm -rf {} +`.
    See `references/stale-pyc-bytecode-example.md` for the full reproduction trace.
   ```bash
   ln -sf ~/.venvs/scrapling/bin/python ~/.local/bin/scrapling-py  # creates symlink
   cat > ~/.local/bin/scrapling-py << 'EOF'  # WRONG! writes through the chain!
   ```
   Instead: always `rm -f symlink` first, then create/rename a regular file.
   ```bash
   rm -f ~/.local/bin/scrapling-py
   cat > /tmp/wrapper.sh << 'EOF'      # write to temp file first
   ...
   EOF
   /bin/cp -f /tmp/wrapper.sh ~/.local/bin/scrapling-py  # regular cp to new path
   chmod +x ~/.local/bin/scrapling-py
   ```
   **Fix when this happens:** If you overwrite a uv-managed Python binary (`~/.local/share/uv/python/<version>/bin/python3.x`):
   ```bash
   rm -rf ~/.local/share/uv/python/cpython-<version>-macos-aarch64-none
   uv python install <version>
   ```
   Then recreate the venv (`uv venv`) and reinstall packages. The same rule applies to write_file tools that may follow symlinks — always verify with `file path` before writing.
   **Related:** Hermes write_file may also follow symlink chains. After writing, verify with `file path && wc -c path` in terminal.

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
- **Dict type aliases** (`references/python-dict-type-aliases.md`) — Python `dict[str, Any]` alias gotcha: attribute access vs subscript access, diagnosis, and bulk-fix workflow for test code.
- **Fixture-model contract repair** (`references/fixture-model-contract-repair.md`) — When test fixtures fail because model APIs changed: read constructors, categorize mismatches (imports / field names / enum values / constructor args), fix bottom-up, validate each layer.
- **pytest collection failure rootdir** (`references/pytest-collection-failure-rootdir.md`) — pytest 9.0.2 CLI `-c /dev/null` breaks rootdir detection → silent "No tests collected" (exit 4). Diagnosis checklist, root cause analysis, and fix approaches.
- **DeepSeek reasoning_content API error** (`references/deepseek-reasoning-content-api-error.md`) — `reasoning_content` must be round-tripped in conversation history for DeepSeek thinking models (v4/reasoner). Error signature, root cause chain, debugging checklist (explicit vs implicit thinking paths, `reasoningEffort: null` trap), and fix options.
