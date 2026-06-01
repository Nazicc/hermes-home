---
name: test-driven-development
description: "RED-GREEN-REFACTOR TDD cycle with test-first approach. Write failing tests before implementation code, then implement minimal code to pass them. Integrates with spec-driven-development, incremental-implementation, and writing-plans."
category: software-development
tags: [tdd, testing, methodology, red-green-refactor]
triggers:
  - write a test
  - tdd
  - test-first
  - red green
  - before writing the implementation
  - smoke test
  - 冒烟测试
anti_triggers:
  - debug
  - already passing
  - one-off script
---

## Purpose

TDD prevents bugs by forcing you to **think through behavior before writing code**. The RED-GREEN-REFACTOR cycle reduces debugging time, creates a living test suite that documents expected behavior, and gives you the confidence to refactor fearlessly — because every test is a safety net.

---

## Core Loop: Red → Green → Refactor

1. **Red** – Write a test for the next small behavior. Run it. It **must** fail.
2. **Green** – Write the **minimum** code to make the test pass. No embellishments.
3. **Refactor** – Clean up the code (and tests) without changing behavior.

---

## Why This Works

### 1. Catches Design Flaws Before They Become Bugs

Writing a test forces you to answer "what should this function do?" before "how should it work?" This surface-level question catches missing edge cases, ambiguous requirements, and API design issues at the cheapest possible moment.

### 2. Creates a Regression Safety Net

Every TDD test is a living document that runs automatically. When you refactor, the test suite tells you immediately if you broke something — not after a code review or in production.

### 3. Prevents Over-Engineering

The "minimum code to pass" discipline prevents speculative generality. You write only what the test demands, nothing more. This keeps codebases lean and focused on actual requirements.

### 4. Improves Test Quality

Tests written first tend to be simpler, more focused, and more meaningful than tests written after implementation. Post-hoc tests often "test the code" (matching implementation structure) rather than "test the behavior" (matching requirements).

---

## RED/GREEN Examples

```python
# tests/test_simplemem.py
import pytest
from simplemem import SimpleMem

def test_memory_stores_items():
    mem = SimpleMem()
    mem.add("hello", {"text": "world"})
    assert "hello" in mem
```

```python
# simplemem.py
class SimpleMem:
    def __init__(self):
        self._store = {}
    def add(self, key, value):
        self._store[key] = value
    def __contains__(self, key):
        return key in self._store
```

### Example: Green Phase — The Minimal Implementation Trap

**Scenario**: You write a test for `parse_email(email: str) -> dict` that extracts `{name, domain}`. Your passing implementation could be:

```python
# ❌ Over-engineered (common mistake)
import re
def parse_email(email: str) -> dict:
    pattern = r'^([\w.+-]+)@([\w-]+\.[\w.]+)$'
    match = re.match(pattern, email)
    if not match:
        raise ValueError(f"Invalid email: {email}")
    return {"name": match.group(1), "domain": match.group(2)}

# ✅ Minimal (TDD discipline)
def parse_email(email: str) -> dict:
    name, domain = email.split("@")
    return {"name": name, "domain": domain}
```

Wait for a second test case (e.g., `test_parse_email_rejects_missing_at_symbol`) before adding validation. TDD builds complexity incrementally — validation is added only when a test demands it.

### Example: Edge Case Discovery via TDD

**Scenario**: Implementing `find_users(role: str) -> list[User]`.

```python
# Test 1 (RED) — nominal case
def test_find_users_by_role():
    users = find_users("admin")
    assert all(u.role == "admin" for u in users)

# Test 2 (RED) — edge case discovered during test writing
def test_find_users_empty_result():
    users = find_users("nonexistent_role")
    assert users == []

# Test 3 (RED) — boundary discovered during test writing
def test_find_users_case_sensitivity():
    users = find_users("ADMIN")
    assert len(users) == 0  # role matching is case-sensitive
```

Writing the tests first revealed two edge cases (empty result and case sensitivity) that might have been missed if implementation came first.

---

## BDD → TDD Workflow (Recommended for Non-Trivial Features)

When starting a feature or module, begin with a BDD spec phase:

1. **Write SPEC.md** — Define the expected behavior, inputs, outputs, edge cases, and constraints in natural language. This is your living document.
2. **Red** — Write tests from the spec. Each test maps to a spec item.
3. **Green** — Implement to make tests pass.
4. **Refactor** — Clean up while keeping all tests green.
5. **Repeat** — Add new spec items and continue.

This integrates with **spec-driven-development**: the spec provides requirements, TDD validates implementation.

---

## Python/pytest Tips

- Place tests in `tests/` directory, use `conftest.py` for shared fixtures.
- Use `pytest --tb=short` for concise failure output.
- Use `pytest -x` to stop at first failure during Red phase.
- Use `pytest --lf` (last-failed) to focus on just-failed tests during debugging.
- Use `pytest.mark.parametrize` for testing multiple inputs.
- **Namespace package conflict**: If `import mypackage` fails but pytest can find it, you may have a namespace package conflict (e.g., a site-packages `mypackage` directory conflicts with your `mypackage` project package). Use `pip install -e .` to ensure the project directory is on `sys.path`, or rename your package to avoid the conflict.

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run a specific test file
pytest tests/test_feature.py

# Run tests matching a pattern
pytest -k "test_name_pattern"
```

---

## Test Structure

```python
def test_feature_behavior():
    """Test that describes expected behavior."""
    # Arrange: Set up inputs and expected outputs
    # Act: Call the function being tested
    # Assert: Verify the output matches expectations
    result = my_function(input_value)
    assert result == expected_output
```

---

## Anti-Patterns (Do NOT Do)

1. **Test-Then-Never-Look-Again** — Writing a test, getting it to pass, and never running it again. Tests must be part of CI and run on every change.
2. **Implementation-First TDD** — Writing the implementation and then adding tests to "prove it works." This produces tests that match the implementation structure rather than the required behavior.
3. **Over-Mocking** — Mocking everything to avoid slow tests. Heavy mocking creates brittle tests that break when implementation details change, not when behavior changes.
4. **Test-Name-Describes-Implementation** — Naming tests after internal methods (`test_should_call_save_method()`) instead of behavior (`test_persists_user_data_after_registration()`).
5. **One Giant Test** — A single test that checks everything. Tests should have a single assertion focus so failures pinpoint exactly what broke.
6. **Skipping Refactor Phase** — Getting Green and declaring "done." Without refactoring, TDD produces working code with technical debt that compounds over iterations.

---

## When NOT to Use

- **One-off scripts** — A script you'll run once and delete. Tests add more time than they save.
- **Documentation-only changes** — Updating a README, adding comments. No behavior changes = no tests needed.
- **Trivial UI tweaks** — Changing a CSS color, adjusting padding. Visual changes are cheaper to verify manually than to set up visual regression tests.
- **Experimental prototyping** — TDD slows down exploration. Prototype first, spec + TDD the real implementation.
- **Hotfixes under time pressure** — Fix the bug, then write a regression test to prevent recurrence.
- **Already-passing legacy code** — Don't retroactively TDD legacy code. Write characterization tests when you need to refactor it.

---

## Quick Checks

- All tests pass? ✓
- Each test has a single, clear assertion focus?
- Test names describe behavior, not implementation?
- No commented-out or skipped tests without reason?
- Coverage is sufficient for the risk level?

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "This is a small change, I don't need to test it" | Smaller changes are the easiest to test — this rationalization is most dangerous for "quick fixes" |
| "I'll add tests later" | Tests written at the end are harder to write and often miss edge cases revealed by writing tests first; later rarely comes |
| "The tests pass in CI, that's enough" | Local test failures often reveal environment-specific issues (namespace packages, sys.path, editable installs) that CI may not catch |
| "Pytest passes, so the code works" | Pytest adds the project root to sys.path — tests may pass in pytest but fail for direct `python -c` invocation. Verify with both. |
| "The tests are just for documentation" | Tests that don't verify behavior are not tests |
| "I understand the code, no need for tests" | Tests document behavior and protect against regressions — understanding doesn't prevent future mistakes |
| "Coverage is good enough" | Coverage metrics measure quantity, not quality of tests |
| "Tests slow me down" | Tests catch bugs early, reducing debugging time — the slowdown is upfront, the speedup is across the lifetime of the code |

---

## Cross-References

- **spec-driven-development** — SDD provides the spec (requirements/scope) that TDD validates via tests. Macro (SDD) + micro (TDD) workflow.
- **incremental-implementation** — Implements code in thin vertical slices, each slice verified by TDD tests. Natural execution partner.
- **writing-plans** — Creates task breakdowns that map each TDD RED cycle to a discrete task.
- **systematic-debugging** — When TDD reveals a failing test you can't immediately fix, use systematic debugging to diagnose the root cause.
