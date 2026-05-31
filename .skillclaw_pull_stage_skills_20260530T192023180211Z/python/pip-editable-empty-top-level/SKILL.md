---
name: pip-editable-empty-top-level
description: "Diagnoses and fixes editable installs where pip succeeds but imports silently fail with ModuleNotFoundError, despite the package directory existing in site-packages. Triggered when a package name contains underscores and pip generates an empty top_level.txt. NOT for cases where the package directory is missing entirely or the package is not installed at all."
category: python
---

# pip Editable Install Empty top_level.txt Bug

## Problem
Editable install (`pip install -e .`) succeeds but `import <package>` fails silently with `ModuleNotFoundError` — even though the package directory exists in `site-packages/`.

## Root Cause
When a package name contains underscores (e.g., `simplemem_evolution`), pip sometimes generates an empty `top_level.txt` inside the package's `.dist-info/` directory. This causes the auto-generated editable finder (`__editable___<name>_finder.py`) to initialize with an empty mapping:

python
MAPPING = {}  # empty because top_level.txt was empty


When Python resolves an import, it calls `find_spec()` on the finder, which looks up the module name in `MAPPING`. Since `MAPPING` is empty, `find_spec()` always returns `None`, and Python treats the package as non-existent rather than raising a clear error — resulting in a silent `ModuleNotFoundError`.

## Fix

### Option 1: Reinstall the package
bash
pip install -e . --no-deps

Re-running the editable install lets pip regenerate the `top_level.txt` file with the correct module name(s).

### Option 2: Patch the editable finder directly
If reinstalling is impractical (e.g., in a production environment), manually inject the correct mapping into the generated finder:

1. Locate the finder file in `site-packages/`:
   bash
   find $(python -c "import site; print(site.getsitepackages()[0])") -name "*finder*" -path "*<package_name>*"
   

2. Open the finder file and find the `MAPPING = {}` line.

3. Replace it with the correct mapping:
   python
   MAPPING = {"<package_name>": "<absolute_path_to_package>"}
   
   Example:
   python
   MAPPING = {"simplemem_evolution": "/Users/can/.hermes/simplemem_evolution"}
   

4. Verify the fix works:
   bash
   python -c "import <package_name>"
   

## Verification Checklist
- [ ] `import <package_name>` succeeds with no output
- [ ] Submodules are importable: `from <package_name> import <submodule>`
- [ ] Run full test suite: `pytest tests/ -v`
