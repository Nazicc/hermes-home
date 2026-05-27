---
name: masked-output-patch-workaround
description: "When a secret value is shown differently masked across tool outputs (e.g., 'sk-cp-...7u5U' in one call and 'sk-cp-...P8g5' in another), string-based patching will fail because the actual bytes differ from what the display shows. Use regex-based replacement via execute_code or a Python heredoc instead of patch tool or simple string.replace. NOT for cases where the secret is consistently masked identically in all outputs — then standard patching works fine."
category: general
---

## Problem

When the framework's output masking redact different parts of the same secret in each tool call, you will see the same value appear as different masked strings across read_file, grep, and patch tool outputs.

Example: The actual key `sk-cp-AJymxdg3vTndxGD7nQ03P8g56NR1kSnNnyGl1yRSGlF16E8zlQ` might show as:
- `sk-cp-...7u5U` in a grep result
- `sk-cp-...P8g5` in a read_file result
- `sk-cp-...nNny` in a Python inspect result

All three are the same key with different segments masked. String-based patching with any of these will fail with `not_found`.

## Solution

Use regex-based replacement via execute_code (preferred) or a Python heredoc executed with `python3 -c` via terminal:

python
import re

with open('/path/to/file') as f:
    content = f.read()

# Replace ANY sk-cp- key with env var reference
pattern = r'api_key:\s*"sk-cp-[^"]*"'
replacement = 'api_key: "$MINIMAX_CN_API_KEY"'

if re.search(pattern, content):
    content = re.sub(pattern, replacement, content)
    with open('/path/to/file', 'w') as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Pattern not found")


Or for simpler cases where you know the exact key suffix/prefix:

python
with open('/path/to/file') as f:
    content = f.read()

old = '  api_key: "sk-cp-...7u5U"'  # whatever masked form you saw
new = '  api_key: "$YOUR_ENV_VAR"'

if old in content:
    content = content.replace(old, new)
    with open('/path/to/file', 'w') as f:
        f.write(content)


## Why execute_code over terminal python heredoc

The execute_code tool operates on actual file bytes without going through the masking pipeline, so regex patterns match the true file content. Terminal-based `python3 -c` heredocs can sometimes still trigger masking on output. The docker exec approach (`docker exec container python3 -c '...'`) also works well for container-internal files.

## What to do after patching

1. Verify with: `grep -n 'api_key.*\$' /path/to/file`
2. Restart any running services that read the config
3. Commit the change to git
4. For Docker containers with volume mounts: changes to host files are immediate; for container-internal files, copy patched file to container or restart container
