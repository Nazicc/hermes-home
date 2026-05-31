---
name: batch-skill-description-audit
description: "Use when batch-updating SKILL.md description frontmatter to add Use-when/Not-for trigger conditions, or when patch tool reports success but changes don't persist. NOT for: one-off single file edits, new skill creation, or when write_file is known to work. For use when the patch tool has been failing in prior runs."
category: general
---

# Batch Skill Description Audit

When updating "Use when..." descriptions across many SKILL.md files, the `patch` tool may report success without persisting changes. Follow this discipline:

## The Read-Before-Patch Discipline

1. **Read first**: Use `read_file(limit=3)` to get the EXACT description line before patching
2. **Use exact strings**: The patch tool requires byte-exact string matching — leading/trailing whitespace, quotes, and YAML delimiters must match exactly
3. **Verify after**: Read the file again to confirm changes persisted
4. **Fall back to write_file**: If patch reports success but read_file shows old content, use `write_file` with the complete modified file content instead

## Pattern for Description Updates

Old format:
yaml
description: "Delegate coding tasks to OpenCode CLI agent..."


New format:
yaml
description: "Use when delegating coding tasks to OpenCode CLI for feature implementation, refactoring, or long-running autonomous sessions. Opencode. NOT for: one-liner edits, trivial changes, or tasks requiring tight iteration loops."


Required elements:
- **Use when...** — specific triggering contexts (2-4 sentences)
- **Skill name capitalized** — in the middle (e.g., "Opencode.")
- **NOT for...** — what this skill is inappropriate for (1-3 sentences)

## Fallback: write_file Method

If patch fails, rewrite the entire file:

1. read_file (no limit) — get full content
2. Modify description in content
3. write_file — write complete modified content
4. read_file(limit=3) — verify new content


## Verification Command

After any batch of patches:
bash
find ~/.hermes/skills -name SKILL.md -exec grep -l "Use when" {} \; | wc -l


Expected: count increases with each successful patch.

## Common Patch Failure Causes

| Cause | Fix |
|---|---|
| Whitespace mismatch | Read exact bytes, include all spaces/quotes |
| YAML multiline | Ensure old_string matches exact YAML scalar format |
| Read cache staleness | Use `limit=3` not full file read before patching |
| File permissions | Check file is writable before patching |

## When to Use write_file Instead

- More than 3 patches on the same file
- Description spans multiple lines
- File has complex YAML that patch can't safely handle
- Patch reports success but verification fails

