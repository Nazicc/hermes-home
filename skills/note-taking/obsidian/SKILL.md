---
name: obsidian
description: "Read, search, and create notes in the Obsidian vault. Trigger signals: user asks to read, search, create, or update an Obsidian note, open a vault, manage vault settings, work with frontmatter, use daily notes, query with Dataview, or interact with Obsidian plugins. NOT for: non-Obsidian note-taking, spanning across multiple vaults without specifying which, or when the Obsidian app UI is more efficient."
category: general
---

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

bash
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

## Vault Structure Conventions


vault/
├── .obsidian/           # config, plugins, workspace.json
├── <folder>/            # user folders
│   └── *.md             # notes (primary content)
├── _assets/             # local attachments (optional)
├── _daily/              # daily notes (if daily-plugin enabled)
└── _templates/          # Templater/templates (if templater-plugin enabled)


Daily notes follow `${VAULT}/_daily/YYYY-MM-DD.md` or `${VAULT}/daily/YYYY-MM-DD.md`.

## S — Sync (Hermes → Obsidian)

When the user asks to sync Hermes knowledge into Obsidian (session history, skills, memories, configs, cron logs, knowledge base):

**Script**: `~/.hermes/scripts/sync-to-obsidian.py` (Python, uses rsync under the hood)

**Vault target**: `_hermes/` subdirectory in the vault root — keeps Hermes data separate from user notes.

**Data sources synced**:
| Source | Path | Description |
|--------|------|-------------|
| Sessions | `sessions/` | 619+ JSONL files (~159M) |
| Skills | `skills/` | 175+ SKILL.md organized by category (~63M) |
| Memories | `memories/` | MEMORY.md, USER.md, Hindsight profile |
| Knowledge base | `knowledge-base/` | OpenViking KB (~1059 files) |
| Cron logs | `cron/` | Cron job output directories |
| Config | `config/` | config.yaml + profiles (~7K files) |

**Vault entry notes**:
- `_hermes/index.md` — root index with stats and directory map (auto-updated)
- `Hermes 知识库.md` at vault root — quick-link entry (auto-created)

**Setup pattern**:
1. Create vault directory skeleton: `_hermes/` with 6 subdirs + index.md
2. Create sync script at `~/.hermes/scripts/sync-to-obsidian.py`
3. Run it once for initial full sync
4. Schedule daily cron: `cronjob action=create name=hermes-obsidian-sync schedule="0 5 * * *" script=sync-to-obsidian.py no_agent=True`

**Cron mode**: Use `no_agent=True` — the script handles everything. No LLM tokens consumed on each run.

**Script anatomy**:
- Uses `rsync -a --delete` for efficient bulk copy
- Handles 6 independent data sources in sequence
- Generates `index.md` with current stats (file counts, sizes, sync time)
- Creates vault root entry note `Hermes 知识库.md` with `[[_hermes/index]]` links
- Quiet on success (~10s for 10K files), loud on failure
- Tries Hindsight MCP API for memory snapshot if service is running

**Pitfalls**:
- Vault path contains spaces — always quote: `"${VAULT}"`
- `rsync` must be installed (macOS has it pre-installed)
- Script path must be under `~/.hermes/scripts/` for cron `no_agent=True` mode (bare filename, no absolute path)
- Large session dir (~159M, 619 files) is the heaviest sync — first run takes ~10s, subsequent rsync runs are nearly instant (only changed files)
- Hindsight MCP snapshot requires the hindsight Docker container running; silent skip if not
- Cron delivery: `no_agent=True` omits LLM, so stdout = message. The script's output lines are sent verbatim — keep them clean and informative.

## Environment Quirks

- **Obsidian URIs**: `obsidian://` URLs can open vaults, notes, and search from CLI:
  `open "obsidian://open?vault=${VAULT_NAME}&file=${NOTE_NAME}"`
- **Frontmatter**: Always use `---` fences. YAML only. Dates in `YYYY-MM-DD` or ISO 8601.
- **Dataview plugin**: Notes must use inline fields (e.g., `due:: 2025-01-20`) or explicit YAML frontmatter. The Dataview plugin must be enabled in `.obsidian/plugins/`.
- **Vault-relative paths**: Obsidian links use `/` as separator. `[[folder/note]]` links relative to current file's folder.
- **Attachments**: Images stored in `_assets/` or same folder. `![[image.png]]` syntax for embedding.

## B — Batch Operations

bash
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

