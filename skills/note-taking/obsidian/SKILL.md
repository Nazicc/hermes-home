---
name: obsidian
description: "Read, search, and create notes in the Obsidian vault. Use when: user asks to read, search, create, or update an Obsidian note, open a vault, manage vault settings, work with frontmatter, use daily notes, query with Dataview, or interact with Obsidian plugins. NOT for: non-Obsidian note-taking, spanning across multiple vaults without specifying which, or when the Obsidian app UI is more efficient."
category: note-taking
triggers:
  - obsidian
  - vault
  - daily note
  - read my notes
  - search notes
anti_triggers:
  - open obsidian app
  - manually
---

## Why This Works

Obsidian is a **local-first knowledge management** system built on plain Markdown files. This design means:

1. **No lock-in** — Every note is a `.md` file. You can open them with any editor, grep/search with standard tools, and version-control with git.
2. **Bidirectional linking** — The `[[wiki-link]]` syntax creates a graph of connected ideas, which makes knowledge discovery emergent — you find things by following links, not just searching keywords.
3. **Plugin extensibility** — Dataview turns frontmatter into a queryable database; Templates/Templater automates note creation; Daily Notes gives you a journal.
4. **Your vault is your API** — Because the vault is just files on disk, MCP tools and bash commands can read/write notes without needing Obsidian to be open.

The core value: **plain files with superpowers**. The simplicity of Markdown files combined with graph-based navigation makes Obsidian ideal for long-term knowledge accumulation (PKM).

## R — Vault Discovery

Before any read/write, determine the vault path:

1. **User-provided path** — if the user specifies a vault path, use it directly.
2. **Common macOS locations** (in order):
   - `~/Library/Containers/pro.shinyfrog.bear/Data/Documents/Bear/Backups/obsidian` — unlikely, verify exists
   - `~/Obsidian/`
   - `~/obsidian/`
   - `~/.obsidian/vaults/`
   - `~/Documents/Obsidian/`
3. **MCP connection** — if using `obsidian_tool` MCP tool, the vault must be open in the Obsidian app.
4. **Validate vault** — a valid Obsidian vault contains `.obsidian/` config directory at root.

## I — Core Operations

**MCP Tools (preferred when available):**

| Operation | Tool | Notes |
|-----------|------|-------|
| Read note | `read_note` | By path or vault-relative path |
| Search notes | `search_notes` | Full-text search within vault |
| Create note | `create_note` | Supports frontmatter, tags |
| Update note | `append_to_note` | Appends; use read-then-write for full replacement |
| Daily notes | `get_daily_note` | Auto-creates if missing |
| Dataview query | Requires Dataview plugin enabled | Use `search_notes` as fallback |

**Bash Fallback (when MCP unavailable):**

```bash
# Read a note
cat "${VAULT}/folder/note-name.md"

# Search notes by content
grep -r "query" "${VAULT}/" --include="*.md" -l

# Search notes by filename
find "${VAULT}/" -name "*query*.md"

# Create note with frontmatter
cat > "${VAULT}/folder/new-note.md" << 'EOF'
---
title: New Note
created: 2025-01-15
tags: [tag1, tag2]
---

# New Note

Content here.
EOF
```

## A1 — Common Triggers

- "read my notes about X"
- "search the vault for Y"
- "create a new note called Z"
- "add frontmatter to this note"
- "open daily note"
- "what's in my vault?"

## A2 — Anti-Triggers

- Never delete notes without explicit user confirmation
- Avoid spanning vaults — ask user to specify which vault
- Dataview queries require the plugin; fall back to `search_notes` if unavailable

## When NOT to Use This Skill

- The user explicitly wants to work in the Obsidian **app UI** (manual editing is faster for complex formatting)
- The task involves **multiple vaults** without specifying which one to target
- The user wants to use a **non-Obsidian** note-taking tool (Bear, Notion, Apple Notes)
- The operation is a **bulk delete or rename** of many files — these are safer done manually or with explicit step-by-step confirmation
- The note content involves **complex embedded media** (Excalidraw canvases, embedded PDFs) that rendering tools can't handle

## Vault Structure Conventions

```
vault/
├── .obsidian/           # config, plugins, workspace.json
├── <folder>/            # user folders
│   └── *.md             # notes (primary content)
├── _assets/             # local attachments (optional)
├── _daily/              # daily notes (if daily-plugin enabled)
└── _templates/          # Templater/templates (if templater-plugin enabled)
```

Daily notes follow `${VAULT}/_daily/YYYY-MM-DD.md` or `${VAULT}/daily/YYYY-MM-DD.md`.

## Examples

### Example 1: Search and Synthesis

**Scenario**: User asks "Find all my notes about Kubernetes networking"

```
grep -rl "kubernetes.*network\|k8s.*network" "${VAULT}/" --include="*.md"
# → discovers 4 notes: k8s-basics.md, networking.md, service-mesh.md, troubleshooting.md
```

Then synthesize: read each note's key points and present a summary to the user.

### Example 2: Create a Meeting Note with Template

**Scenario**: User says "Create a note for today's standup"

```bash
today=$(date +%Y-%m-%d)
cat > "${VAULT}/_daily/${today}-standup.md" << NOTE
---
title: Standup ${today}
created: ${today}
tags: [standup, daily]
---

# Standup — ${today}

## What I did yesterday

## What I'll do today

## Blockers
NOTE
```

### Example 3: Frontmatter Bulk Update

**Scenario**: User says "Add tag `[archive]` to all meeting notes from 2024"

```bash
for f in "${VAULT}"/meetings/*.md; do
  # Check if note is from 2024 via frontmatter
  if grep -q "date: 2024-" "$f"; then
    # Add archive tag to frontmatter (simplified — use sed for real cases)
    echo "Tagged: $f"
  fi
done
```

## Environment Quirks

- **Obsidian URIs**: `obsidian://` URLs can open vaults, notes, and search from CLI:
  `open "obsidian://open?vault=${VAULT_NAME}&file=${NOTE_NAME}"`
- **Frontmatter**: Always use `---` fences. YAML only. Dates in `YYYY-MM-DD` or ISO 8601.
- **Dataview plugin**: Notes must use inline fields (e.g., `due:: 2025-01-20`) or explicit YAML frontmatter. The Dataview plugin must be enabled in `.obsidian/plugins/`.
- **Vault-relative paths**: Obsidian links use `/` as separator. `[[folder/note]]` links relative to current file's folder.
- **Attachments**: Images stored in `_assets/` or same folder. `![[image.png]]` syntax for embedding.

## B — Batch Operations

```bash
# Create multiple notes from a template
for name in "note-a" "note-b" "note-c"; do
  cat > "${VAULT}/${name}.md" << EOF
---
title: ${name}
created: $(date +%Y-%m-%d)
tags: [auto]
---

# ${name}
EOF
done

# Tag-based search
grep -r "^tags:.*\[${TAG}\]\|^tags:.*${TAG}" "${VAULT}/" --include="*.md" -l
```

## E — Error Handling

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `No such file` on vault path | Vault not found at expected location | Run detection flow; ask user for path |
| Empty frontmatter parsed | `.obsidian/` config missing | Not a valid vault; skip or warn |
| `obsidian://` URI not working | Vault name mismatch | Use exact vault name as shown in app |
| MCP connection fails | Vault not open in Obsidian app | Prompt user to open Obsidian first |
| Vault path contains spaces | Path not quoted | Use quoted path strings |
| Large vault (>10k notes) | Performance degradation | Prefer `search_notes` over recursive reads |
| Concurrent edits | Multiple instances running | Obsidian MCP is single-user; warn if multiple instances |

## Cross-References

- `llm-wiki` — Building a persistent markdown knowledge wiki (complementary to Obsidian notes)
- `mem-search` — Three-layer memory search protocol for knowledge retrieval
- `memento-flashcards` — Spaced-repetition flashcards that can reference Obsidian notes
- `apple-notes` — Apple Notes integration (alternative note-taking system)
- `siyuan` — SiYuan Note API (alternative PKM tool)
