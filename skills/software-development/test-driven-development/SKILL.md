---
name: test-driven-development
description: "Use when implementing any feature or bugfix, before writing implementation code. Enforces RED-GREEN-REFACTOR cycle with test-first approach and optional BDD spec-first phase (write SPEC.md first, then tests until RED, then code until GREEN). NOT for: one-off scripts, documentation-only changes, or trivial changes where tests provide no value."
category: general
trigger: [write a test, tdd, test-first, red green, before writing the implementation, "\u5192\u70DF\u6D4B\u8BD5", smoke test, "\u4EE3\u7801\u5185\u5316.*\u6D4B\u8BD5", "\u8865\u5168\u6D4B\u8BD5", "\u91CD\u5199\u6D4B\u8BD5", retrofit test, "\u73B0\u6709\u4EE3\u7801.*\u6D4B\u8BD5"]
anti_trigger: [debug, already passing, one-off script, "\u65B0\u5EFA\u9879\u76EE"]
anti_trigger: [debug, already passing, one-off script]
---

# Test-Driven Development (TDD)

## Core Loop: Red → Green → Refactor

1. **Red** – Write a test for the next small behavior. Run it. It must fail.
2. **Green** – Write the minimum code to make the test pass. No embellishments.
3. **Refactor** – Clean up the code (and tests) without changing behavior.

### Red — Write a failing test

Before writing any implementation code:
1. Write a test that describes the expected behavior
2. Run the test and confirm it fails
3. Write only enough code to make the test pass

### Green — Write the minimal implementation

When the test is failing:
1. Write the simplest code that makes the test pass
2. Do not optimize or add features beyond what the test requires
3. Focus on correctness over completeness

### Refactor — Improve without changing behavior

When tests are passing:
1. Improve code structure, remove duplication, clarify names
2. Ensure all tests still pass after refactoring
3. Do not add new functionality during refactor

## RED/GREEN Examples

python
# tests/test_simplemem.py
import pytest
from simplemem import SimpleMem

def test_memory_stores_items():
    mem = SimpleMem()
    mem.add("hello", {"text": "world"})
    assert "hello" in mem


python
# simplemem.py
class SimpleMem:
    def __init__(self):
        self._store = {}

    def add(self, key, value):
        self._store[key] = value

    def __contains__(self, key):
        return key in self._store


## Retrofitting Tests to Existing Code

When adding/fixing tests for **code that already exists** (not greenfield TDD), the primary failure mode is **API signature drift** — tests assume method signatures, parameter names, or class constructors that don't match the actual implementation.

**Protocol:** Read every source file → verify all class constructors with `inspect.signature()` → build a mapping table of `(what tests assume → what API actually is)` → fix all mismatches in one batch before running pytest.

Full reference: `references/retrofitting-tests-to-existing-code.md` — includes the two-layer verification protocol, common drift categories table, and recovery workflow.

## BDD→TDD Workflow (Recommended for Non-Trivial Features)

When starting a feature or module, begin with a BDD spec phase:

1. **Write SPEC.md** – Define the expected behavior, inputs, outputs, edge cases, and constraints in natural language. This is your living document.
2. **Red** – Write tests from the spec. Each test maps to a spec item.
3. **Green** – Implement to make tests pass.
4. **Refactor** – Clean up while keeping all tests green.
5. **Repeat** – Add new spec items and continue.

## Python/pytest Tips

- Place tests in `tests/` directory, use `conftest.py` for shared fixtures.
- Use `pytest --tb=short` for concise failure output.
- Use `pytest -x` to stop at first failure during Red phase.
- Use `pytest --lf` (last-failed) to focus on just-failed tests during debugging.
- Use `pytest.mark.parametrize` for testing multiple inputs.
- **Namespace package conflict**: If `import mypackage` fails but pytest can find it, you may have a namespace package conflict (e.g., a site-packages `mypackage` directory conflicts with your `mypackage` project package). In that case, use `pip install -e .` (editable install) to ensure the project directory is on `sys.path`, or rename your package to avoid the conflict.

### Diagnosing "No tests collected" (silent skip)

Pytest can silently report "No tests collected" (exit code 4) even when your test file is syntactically valid. This is NOT the same as a test failure (exit code 1) — it means pytest couldn't find any test functions to run.

**Two-layer diagnostic:**

```
Layer 1 — Check the test file itself:
  python -c "import ast; ast.parse(open('tests/test_*.py').read()); print('AST OK')"
  python -c "import test_module"   # confirm the module imports without error

Layer 2 — Check pytest collection:
  pytest tests/test_*.py -v --collect-only   # verbose collection output
  echo $?   # exit code 4 = collection error, 0/5 = no tests found
  python -m pytest tests/ -v --log-cli-level=DEBUG   # see why files were skipped
```

**Common root causes:**

| Symptom | Root Cause | Fix |
|---|---|---|
| `python -c "import test_module"` succeeds but `pytest tests/test_*.py` collects nothing | Package not installed in editable mode (pytest 9.x is stricter about this) | `pip install -e .` |
| `python -c "import test_module"` fails | Test file has an import error | Fix the import or install missing deps |
| `--collect-only` shows files but 0 tests | No functions named `test_*` in file | Rename functions or add `test_` prefix |
| `--log-cli-level=DEBUG` shows "skipped" with collection error | conftest.py has a silent import error upstream | Check conftest.py's conftest.py for circular imports |
| `pytest tests/` passes but `pytest single_file.py` doesn't | conftest.py from parent `tests/` not loaded | Run from project root with `python -m pytest` |

### Running Tests

bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run a specific test file
pytest tests/test_feature.py

# Run tests matching a pattern
pytest -k "test_name_pattern"


## Test Structure

python
def test_feature_behavior():
    """Test that describes expected behavior."""
    # Arrange: Set up inputs and expected outputs
    # Act: Call the function being tested
    # Assert: Verify the output matches expectations
    result = my_function(input_value)
    assert result == expected_output


## Quick Checks

- All tests pass? ✓
- Each test has a single, clear assertion focus?
- Test names describe behavior, not implementation?
- No commented-out or skipped tests without reason?
- Coverage is sufficient for the risk level?

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "This is a small change, I don't need to test it" | Smaller changes are the easiest to test — this rationalization is most dangerous for "quick fixes" |
| "I'll add tests later" / "I'll test at the end" | Tests written at the end are harder to write and often miss edge cases revealed by writing tests first; later rarely comes, test debt compounds |
| "The tests pass in CI, that's enough" | Local test failures often reveal environment-specific issues (namespace packages, sys.path, editable installs) that CI may not catch |
| "Pytest passes, so the code works" | Pytest adds the project root to sys.path — tests may pass in pytest but fail for direct `python -c` invocation due to import path differences. Verify with both. |
| "The tests are just for documentation" | Tests that don't verify behavior are not tests |
| "I understand the code, no need for tests" | Tests document behavior and protect against regressions — understanding doesn't prevent future mistakes |
| "Coverage is good enough" | Coverage metrics measure quantity, not quality of tests |
| "Tests slow me down" | Tests catch bugs early, reducing debugging time — the slowdown is upfront, the speedup is across the lifetime of the code |
