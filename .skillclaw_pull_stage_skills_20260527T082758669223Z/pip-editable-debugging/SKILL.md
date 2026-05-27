---
name: pip-editable-debugging
description: "Debug `pip install -e` scenarios where pip reports success but `python -c \"import <package>\"` raises ModuleNotFoundError, while pytest may still find the package. Handles editable install finder corruption (empty MAPPING dict), missing top_level.txt entries, namespace package conflicts, and missing __init__.py files. Also useful when different Python environments see the package differently. NOT for: syntax errors, missing requirements.txt entries, non-editable installs, missing build dependencies, or packages with broken source layouts."
category: general
---

# pip editable install debugging

## Problem
`pip install -e /path/to/package` succeeds but `python -c "import package"` fails with `ModuleNotFoundError`, while pytest finds it fine.

## Root Cause
Editable installs generate a `__editable__*.py` finder in `site-packages/`. If the installer's `top_level.txt` (which lists top-level package names) is empty, pip generates a finder with an empty `MAPPING` dict — the import system finds the finder but MAPPING has no entries, so the import fails silently.

## Diagnostic Steps

### Step 1: Verify the failure

bash
python -c "import <package_name>"


Confirm it fails with `ModuleNotFoundError` or `ImportError`.

### Step 2: Check pytest vs. python discrepancy

bash
pytest --collect-only 2>&1 | grep -i <package_name>
python -c "import <package_name>"


If pytest finds it but bare python does not, the editable install is broken for the standard import system.

### Step 3: Verify package is installed in the correct venv

bash
~/.hermes/hermes-agent/venv/bin/python -m pip show <package-name>


Check the "Location" field — it should be the hermes-agent venv site-packages.

### Step 4: Locate the editable finder

**Portable method (preferred):**
bash
python -c "import site; print(site.getsitepackages())"
ls $(python -c "import site; print(site.getsitepackages()[0])") | grep __editable__


**Hermes-agent venv explicit path:**
bash
ls ~/.hermes/hermes-agent/venv/lib/python3.11/site-packages/ | grep <package>


Editable installs appear as:
- `__editable__<package>-*.py` (finder file)
- `__editable__<package>-*.pth` (newer pip)
- `<package>.pth` (manual path file)

### Step 5: Inspect the finder's MAPPING dict

bash
FINDER=$(ls $(python -c "import site; print(site.getsitepackages()[0])")/ | grep __editable__ | grep -i <package>)
cat "$(python -c 'import site; print(site.getsitepackages()[0])')/$FINDER"


**Broken example:**
python
MAPPING: dict[str, str] = {}


**Working example:**
python
MAPPING: dict[str, str] = {'simplemem_evolution': '/Users/can/.hermes/simplemem_evolution'}


### Step 6: Confirm via top_level.txt

bash
DIST=$(ls $(python -c "import site; print(site.getsitepackages()[0])")/ | grep -E '<package>.*\.dist-info' | head -1)
cat "$(python -c 'import site; print(site.getsitepackages()[0])')/$DIST/top_level.txt"


An empty `top_level.txt` confirms the issue.

### Step 7: Dump MAPPING programmatically

bash
FINDER=$(find ~/.hermes/hermes-agent/venv/lib/python*/site-packages/ \
  -name "__editable___<package>_*.py" 2>/dev/null | head -1)

python -c "
import sys, importlib.util
sys.path.insert(0, '$(python -c 'import site; print(site.getsitepackages()[0])')')
spec = importlib.util.spec_from_file_location('_finder', '$FINDER')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('MAPPING contents:', mod.MAPPING)
print('MAPPING empty:', len(mod.MAPPING) == 0)
"


Expected output if broken: `MAPPING contents: {}`

## Fix Strategies

### Fix A: Reinstall the editable package

bash
cd <project-directory>
pip install -e . --no-build-isolation


Or with explicit venv binary:
bash
cd <project-directory>
~/.hermes/hermes-agent/venv/bin/python -m pip install -e . --no-build-isolation


### Fix B: Create a manual .pth file

If Fix A doesn't work, create a `.pth` file directly:
bash
echo '/path/to/project/directory' > ~/.hermes/hermes-agent/venv/lib/python3.11/site-packages/<package_name>.pth


### Fix C: Patch the Finder MAPPING directly

If `MAPPING` is empty, edit the finder file in-place:

bash
PKG_PATH=$(realpath /path/to/your/package)
FINDER=$(ls $(python -c "import site; print(site.getsitepackages()[0])")/ | grep __editable__ | grep -i <package>)

python << EOF
import re, pathlib

finder_path = pathlib.Path("$(python -c 'import site; print(site.getsitepackages()[0])')/$FINDER")
content = finder_path.read_text()

# Patch the MAPPING declaration
patched = re.sub(
    r'(MAPPING\s*:\s*dict\[str,\s*str\]\s*=\s*)\{\s*\}',
    r'\1{"<package>": "$PKG_PATH"}',
    content,
    flags=re.DOTALL
)

if patched == content:
    patched = re.sub(
        r'(MAPPING\s*=\s*)\{\}',
        rf'\1{{"<package>": "{PKG_PATH}"}}',
        content
    )

finder_path.write_text(patched)
print('Patch applied')
EOF


### Fix D: Check for namespace package conflicts

If both `parent` (installed) and `parent_child` (editable) exist as namespace packages under the same `parent/` directory in site-packages, Python finds the installed `parent` first and fails to traverse into `parent_child`.

**Signs**: `import parent_child` raises `ModuleNotFoundError` but `import parent` succeeds.

**Fix**: Rename the project package or uninstall the conflicting namespace package.

## If the Finder Doesn't Exist at All

The package may have been installed non-editable. Check:
bash
pip show <package_name>  # look for Location:
pip list -e | grep <package_name>  # should show editable package


If not editable, reinstall:
bash
pip uninstall <package_name>
pip install -e /path/to/package


## If MAPPING Is Correct but Import Still Fails

- Check for missing `__init__.py` in the package directory
- Verify the package directory is listed in `sys.path`
- Try reinstalling the package's dependencies
- Clear stale bytecode: `find . -type d -name __pycache__ -exec rm -rf {} +`

## Verification Checklist

After fixing, verify in this order:

1. **Import works** — `python -c "import <package>"` succeeds
2. **Correct path** — `python -c "import <package>; print(<package>.__file__)"` prints project directory path (not site-packages)
3. **Pytest passes** — all unit tests pass
4. **Integration tests pass** — run smoke/integration tests (a clean import + pytest pass does NOT guarantee the package is fully functional; downstream integration tests can surface API mismatches, missing required Pydantic fields, or wrong method signatures)

## Quick Reference

| Check | Command |
|---|---|
| Import via python binary | `~/.hermes/hermes-agent/venv/bin/python -c "import <package>"` |
| Import via pytest | `~/.hermes/hermes-agent/venv/bin/python -m pytest --collect-only` |
| Package file location | `python -c "import <package>; print(<package>.__file__)"` |
| Installed as editable | `pip list -v \| grep <package>` |

## Common Patterns

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` after `pip install -e` | Empty MAPPING in finder | Reinstall or patch MAPPING |
| Pytest works, python import fails | Venv python vs pytest python mismatch | Use same binary for both |
| Works in shell, fails in subprocess | Stale `.pyc` or `__pycache__` | Clear cache: `find . -type d -name __pycache__ -exec rm -rf {} +` |
| Works manually, fails in CI | Non-reproducible install state | Pin pip version, use `pip freeze` |
| Finder file missing entirely | Installed non-editable | Reinstall with `-e` flag |
| Subpackage import fails | Namespace package conflict | Rename or uninstall conflicting package |

## Why This Happens

Editable installs work by recording a mapping in a finder file. If pip's build backend fails silently or the project has no top-level packages (only subpackages), the MAPPING can be left empty. Python then falls back to site-packages search, where it may find a conflicting namespace package or nothing at all.
