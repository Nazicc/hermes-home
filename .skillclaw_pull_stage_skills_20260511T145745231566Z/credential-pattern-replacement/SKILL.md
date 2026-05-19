---
name: credential-pattern-replacement
description: "Replace masked or redacted credentials in config files when the redaction system shows different parts of the same value in different tool outputs. NOT for cases where the credential is fully visible — use direct string replacement in those cases. Triggered when patching API keys or tokens that appear partially masked (e.g., `sk-cp-...XXXX` in tool output) and exact string matching fails."
category: general
---

## Problem

When the system redaction layer masks credentials, it may display **different suffixes of the same key** in different tool outputs. For example:
- Tool A output: `api_key: "sk-cp-...7u5U"`
- Tool B output: `api_key: "sk-cp-...P8g5"`
- Tool C output: `api_key: "sk-cp-...nNny"`

These are the **same key**, but the redaction system shows only the end portion, and it varies between calls.

## Solution

Use **regex** to match the credential by pattern rather than by literal string:

python
import re

with open('/path/to/config.yaml') as f:
    content = f.read()

# Match any api_key with value starting with sk-cp-
pattern = r'(api_key:\s*)"sk-cp-[^"]*"'
replacement = r'\1"$ENV_VAR_NAME"'

if re.search(pattern, content):
    new_content = re.sub(pattern, replacement, content)
    with open('/path/to/config.yaml', 'w') as f:
        f.write(new_content)
    print("Patched successfully")
else:
    print("Pattern not found — key may already be replaced or use different format")


## Key Pattern

The regex `sk-cp-[^\"]*` matches any value starting with `sk-cp-` and containing any non-quote characters until the closing quote. This works regardless of which suffix the redaction layer happens to display.

## Alternative: Byte-level Search

If regex still fails, search for the raw bytes of the key prefix:

python
with open('/path/to/config.yaml', 'rb') as f:
    content = f.read()

idx = content.find(b'api_key: sk')
if idx >= 0:
    print(repr(content[idx:idx+50]))  # See actual surrounding bytes


## Don't Use

- `patch` tool with the masked string (it won't match)
- `str.find('sk-cp-...7u5U')` (the displayed suffix varies)
- Direct string replacement of the masked value

## Trigger Context

This skill applies when:
- Patching API keys or secrets in YAML/JSON config files
- Tool output shows `...` ellipsis in a credential value
- Different tool calls show different suffixes of the same credential
- Both `patch` tool and string `in` checks return "not found" despite the value being visibly present in output
