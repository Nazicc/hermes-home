---
name: hermes-evolver-integration
description: "Integrate Hermes Agent with Evolver (NousResearch/hermes-agent-self-evolution) via lightweight bridge — sync Hermes session logs to Evolver's scan directory, run GEPA optimization dry-run to validate setup, and optionally trigger full evolution runs."
tags: [hermes, evolver, evolution, bridge, experiments]
related_skills: [hermes-agent, systematic-debugging, native-mcp, deerflow-hermes-integration]
---

## Teaching: Why This Works

### Systematic Session Evolution

The Hermes ↔ Evolver integration follows a three-step pipeline that mirrors the scientific method: **collect data → analyze → apply insights**.

**Step 1 (Bridge):** Hermes accumulates session logs in `state.db`. The bridge script extracts these as structured JSON files into Evolver's scan directory — this is the data collection phase. By running every 4 hours via cron, it builds a growing dataset of actual agent usage.

**Step 2 (GEPA):** Evolver's Genetic Evolutionary Prompt Algorithm reads these session files and applies mutation/crossover operations to find better prompt strategies. Each cycle produces candidate improvements (`capsules.json`) and tracks quality metrics over time (`rtk_metrics.jsonl`) — this is analysis.

**Step 3 (Forward):** Successful evolution results should feed back into the agent's reputation store (SimpleMem Evolution) to close the loop. Currently this step is implemented via SQLite INSERT, but the full hook-based pipeline (gep_recall/gep_record_outcome/finalize_and_decay) is documented and ready for future implementation.

### Why the Three-Phase Architecture Matters

Separation of concerns: the bridge doesn't run evolution, and the evolution engine doesn't write to agent memory. Each component can fail or be upgraded independently. A bridge failure doesn't corrupt the evolution store; a GEPA crash doesn't delete session logs.

### The Config Override Trap

SkillClaw's `_configure_hermes` overwrites `config.yaml` on every `hermes mcp add` / `hermes config set` / install. Understanding this single fact prevents the most common integration failure mode — config loss after tweaks. The workaround (editing `config.yaml.d/` or restoring via script) is built into the integration's operational model.

## Examples

### Example 1: Fresh Integration — From Zero to Running Cycle

**Scenario:** You've just cloned the evolver repo and want to verify the full pipeline works end-to-end.

**Steps:**
```bash
# 1. Verify prerequisites
ls ~/.hermes/hermes-agent/hermes-agent-self-evolution/ || echo "Clone needed"
ls ~/.hermes/hermes-agent/scripts/hermes_to_evolver_bridge.py || echo "Bridge missing"

# 2. Dry-run bridge (safe, no side effects)
cd ~/.hermes/hermes-agent
python3 scripts/hermes_to_evolver_bridge.py --dry-run
# → "Would sync 47 sessions to /Users/can/.openclaw/agents/hermes-agent/sessions/"

# 3. Actually sync (now that dry-run confirmed it works)
python3 scripts/hermes_to_evolver_bridge.py --full-sync
# → "Synced 47 sessions to /Users/can/.openclaw/agents/hermes-agent/sessions/"

# 4. Verify scan directory populated
ls ~/.openclaw/agents/hermes-agent/sessions/ | wc -l
# → 47 (matches dry-run count)
```

**Outcome:** Full bridge pipeline verified in 4 commands. Dry-run prevents accidental writes during first-time setup.

### Example 2: Config Loss After hermes mcp add

**Scenario:** You added a new MCP server via `hermes mcp add openviking`, and suddenly the evolver integration breaks with API key errors.

**Diagnosis:**
```bash
# 1. Check if config was overwritten
diff ~/.hermes/config.yaml ~/.hermes/config.yaml.bak
# → Lines differ: the OPENAI_API_BASE override is missing

# 2. Confirm SkillClaw was the culprit
grep "MINIMAX_API_KEY" ~/.hermes/config.yaml
# → Not found (was there before the mcp add)

# 3. Restore from backup
/bin/cp -f ~/.hermes/config.yaml.bak ~/.hermes/config.yaml
```

**Root Cause:** SkillClaw's `_configure_hermes` rewrites `config.yaml` on every `hermes mcp add`. The custom evolver provider config was in the file but not preserved.

**Prevention:** Add custom provider configs to `~/.hermes/config.yaml.d/` instead of directly in `config.yaml`.

### Example 3: Verifying Step 3 Gap (Evolution Not Written to SimpleMem)

**Scenario:** After running GEPA cycles, you check `events.jsonl` and see data, but the SimpleMem Evolution Store is empty.

**Diagnosis:**
```bash
# 1. Confirm GEPA is producing events
cat ~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/events.jsonl | wc -l
# → 142 events exist

# 2. Check SimpleMem evolution store
sqlite3 ~/.hermes/simplemem_evolution/evolution.db "SELECT COUNT(*) FROM evolution_entries;"
# → 0 (nothing written)

# 3. Confirm the evolver_to_simplemem.py script exists
ls ~/.hermes/hermes-agent/scripts/evolver_to_simplemem.py
# → No such file (Step 3 not implemented)
```

**Root Cause:** The documented Step 3 bridge (`evolver_to_simplemem.py`) has not been created yet. GEPA produces `events.jsonl` but nothing reads it into SimpleMem.

**Mitigation:** Either implement the script from the documentation below, or check `events.jsonl` manually to verify GEPA is working.

## Anti-Patterns

### 🔴 Editing config.yaml Directly When SkillClaw Manages It
Manually editing `~/.hermes/config.yaml` to add custom provider configs, only to have SkillClaw's `_configure_hermes` overwrite them on the next `hermes mcp add`, `hermes config set`, or install.

**Fix:** Add custom overrides to `~/.hermes/config.yaml.d/` (which is merged into the main config after SkillClaw runs), or re-apply changes via `restore_hermes_config.sh`. Never edit `config.yaml` directly if you use SkillClaw.

### 🔴 GEPA Only Optimizes Predictor Instructions — Not Full Skill Bodies

The GEPA optimizer in `hermes-agent-self-evolution` only operates on `predictor.signature.instructions` — a 200–800 character string. The full skill body (which can be 40,000+ characters) is discarded during optimization:

- A skill like `hermes-agent` (45K chars of teaching content) gets compressed into ~211 chars of predictor instructions
- The optimizer cannot rewrite skill examples, add anti-patterns, or improve pedagogical quality
- Fitness scores measure whether a pared-down instruction string works, not whether the full skill improves

**Impact:** 16 evolution runs showed only +0.009 absolute improvement on average (baseline 0.604 → 0.613), with 56.3% positive, 18.8% regression, 25% no-change. The output-scope limitation is the primary suspect.

**Diagnosis:**
```bash
cd ~/.hermes/hermes-agent/hermes-agent-self-evolution
python3 -c "
import json
caps = json.load(open('assets/gep/capsules.json'))
for c in caps:
    inst = c.get('content', {}).get('instruction', '')
    print(f'Instruction length: {len(inst)} chars')
"
```

**Fix:** Extend `evolve_skill.py`'s `mutate_skill()` and `crossover_skills()` to operate on full skill body sections (Examples, Anti-Patterns, Teaching), not just the `instruction` field. Or implement a two-stage pipeline: Stage 1 optimizes instructions, Stage 2 rewrites the full skill body based on those instructions.

See `references/16-run-analysis.md` for full statistical breakdown.

### 🔴 Assuming GEPA Hook Functions Exist
Reading the skill documentation and treating `gep_recall`, `gep_record_outcome`, and `finalize_and_decay` as callable functions when they are placeholder names — not implemented in the Hermes agent codebase.

**Fix:** The only reliable write path is SQLite `INSERT OR IGNORE` directly into `evolution.db`. Verify by grepping: `grep -r "gep_recall\|gep_record_outcome\|finalize_and_decay" ~/.hermes/hermes-agent/ | wc -l` should return 0.

### 🔴 Using `python` Instead of `python3` on macOS
On MacBooks, the default `python` command may not exist or may point to Python 2. All bridge scripts and GEPA commands hardcode `python3`, but cron jobs or ad-hoc commands may use bare `python`.

**Fix:** Always use `python3` explicitly in scripts, cron commands, and terminal sessions. Verify: `which python3` should return a valid path.

### 🔴 Running Full Sync on Every Cron Tick
The bridge's `--full-sync` flag syncs *all* sessions every time. Over time, with hundreds of sessions, this becomes slow and redundant — most sessions haven't changed between 4-hour ticks.

**Fix:** Use the default behaviour (sync recent 50 sessions) for regular cron runs. Only use `--full-sync` for initial setup or after manual cleanup of the scan directory.

## When NOT to Use This Skill

- **For simple session recall** — use SimpleMem MCP `memory_search` or `session_search` instead
- **For non-Hermes agent evolver setups** — this integration is specific to Hermes Agent's state.db format and cron infrastructure
- **For skill authoring without evolver** — use skill\_manage directly; the evolver pipeline is only needed for automated evolution
- **For debugging GEPA algorithm internals** — this skill covers the integration pipeline (bridge → files → store), not the GEPA genetic algorithm itself
- **For single-step evolution testing** — use the evolve server's `--dry-run` flag instead of triggering full cycles
- **When SkillClaw is not installed** — the config override workaround section is irrelevant; you can edit `config.yaml` normally

## Cross-References

- [hermes-agent](/skills/hermes-agent/SKILL.md) — Hermes Agent core config, MCP, and CLI reference
- [systematic-debugging](/skills/debugging/systematic-debugging/SKILL.md) — Debugging methodology: hypothesis → isolate → fix → verify
- [native-mcp](/skills/mcp/native-mcp/SKILL.md) — Register MCP servers in Hermes config.yaml
- [deerflow-hermes-integration](/skills/deerflow-hermes-integration/SKILL.md) — Alternative multi-agent integration with DeerFlow
- [hermes-agent-architecture](/skills/software-development/hermes-agent-architecture/SKILL.md) — Hermes Agent project architecture

---

## Architecture

```
Hermes state.db
    ↓ Step 1: hermes_to_evolver_bridge.py (cron every 4h)
~/.openclaw/agents/hermes-agent/sessions/
    ↓ Step 2: Evolver GEPA (python3 process, independent of Hermes)
~/.hermes/hermes-agent/hermes-agent-self-evolution/
    assets/gep/
    ├── events.jsonl       ← EvolutionEvents + ValidationReports
    ├── capsules.json       ← Approved gene diffs (PENDING review)
    ├── rtk_metrics.jsonl   ← Per-session RTK scores
    └── signals.json        ← errsig detection output
    ↓ Step 3: evolver_to_simplemem.py (MISSING — see implementation below)
SimpleMem Evolution Store (~/.hermes/simplemem_evolution/evolution.db)
```

**RTK (Runtime Kernel) metrics** track signal/quality scores over time, logged to:
`~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/rtk_metrics.jsonl`

Each line is a JSON object with: `timestamp`, `session_id`, `signal_score`, `quality_score`, `tokens_used`.

```bash
tail -5 ~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/rtk_metrics.jsonl | jq
```

### Key Paths

| Component | Path |
|-----------|------|
| Hermes state.db | `~/.hermes/state.db` |
| Evolver scan dir | `~/.openclaw/agents/hermes-agent/sessions/` |
| Evolver GEPA output | `~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/` |
| Evolver bridge script | `~/.hermes/hermes-agent/scripts/hermes_to_evolver_bridge.py` |
| SimpleMem Evolution DB | `~/.hermes/simplemem_evolution/evolution.db` |
| Cron job | "Hermes-Evolver Bridge + Analysis" (job_id: `6cf04f3139de`, every 4h) |

### Local Hooks (Claude Code)

- `~/.claude/hooks/evolver-session-start.js` — runs before each Claude Code session
- `~/.claude/hooks/evolver-session-end.js` — records outcome after each session
- `~/.claude/hooks/evolver-signal-detect.js` — detects improvement opportunities

**Status as of 2026-04:**
- Step 1 (session sync) ✓ working
- Step 2 (GEPA cycles) ✓ working
- Step 3 (Evolver → SimpleMem) ✗ NOT YET BUILT — evolver produces results but they are not written to the SimpleMem Evolution Store

---

## Prerequisites

### Network: ARK Volcengine Endpoint (NOT `api.openai.com`)

If `api.openai.com` is unreachable (TLS timeout), set `OPENAI_API_BASE` and `OPENAI_API_KEY` in `~/.hermes/hermes-agent/.env`:

```bash
echo 'OPENAI_API_BASE=https://ark.cn-beijing.volces.com/api/coding/v3' >> ~/.hermes/hermes-agent/.env
echo 'OPENAI_API_KEY=your-ark-api-key' >> ~/.hermes/hermes-agent/.env
```

The `evolve.js` Node CLI hardcodes `api.openai.com`, but `dotenv` loads `OPENAI_API_BASE` at startup, overriding the hardcoded value before any HTTP calls are made. No JavaScript patching required.

**Verify connectivity:**
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer <your-ark-key>" \
  https://ark.cn-beijing.volces.com/api/coding/v3/models
```
Expected: `200`

### Platform: Use `python3`, NOT `python`

On MacBooks, the default `python` command may not exist. Always use `python3` explicitly in scripts and cron commands.

---

## Quick Start

### 1. Verify Prerequisites

```bash
# Check evolver repo is cloned
ls ~/.hermes/hermes-agent/hermes-agent-self-evolution/

# Check bridge script exists
ls ~/.hermes/hermes-agent/scripts/hermes_to_evolver_bridge.py

# Check sessions are syncing
ls ~/.openclaw/agents/hermes-agent/sessions/ | wc -l  # should be > 0

# Check evolver process running
ps aux | grep evolve_server | grep -v grep
```

### 2. Run Bridge Manually

```bash
cd ~/.hermes/hermes-agent/hermes-agent-self-evolution
OPENAI_API_BASE=https://ark.cn-beijing.volces.com/api/coding/v3 \
OPENAI_API_KEY=your_ark_api_key \
python3 scripts/hermes_to_evolver_bridge.py --full-sync
```

### 3. Verify Scan Directory

```bash
ls ~/.openclaw/agents/hermes-agent/sessions/ | head
```

---

## Step 1: Bridge Script

**Location:** `~/.hermes/hermes-agent/scripts/hermes_to_evolver_bridge.py`

The bridge syncs Hermes session logs from `~/.hermes/state.db` → `~/.openclaw/agents/hermes-agent/sessions/` (Evolver's scan directory).

```python
#!/usr/bin/env python3
"""Bridge: Hermes state.db → Evolver scan directory."""
import sqlite3, json, os, argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # Load OPENAI_API_BASE and OPENAI_API_KEY from .env

BRIDGE_DIR = Path(os.environ.get(
    "HERMES_BRIDGE_DIR",
    "~/.openclaw/agents/hermes-agent/sessions"
)).expanduser()
STATE_DB = Path(os.environ.get("HERMES_STATE_DB", "~/.hermes/state.db")).expanduser()

def read_hermes_sessions(limit=50, full_sync=False):
    conn = sqlite3.connect(STATE_DB)
    cur = conn.cursor()
    if full_sync:
        cur.execute("SELECT session_id, started_at, ended_at, summary FROM sessions ORDER BY started_at ASC")
    else:
        cur.execute("SELECT session_id, started_at, ended_at, summary FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "started_at": r[1], "ended_at": r[2], "summary": r[3]} for r in rows]

def write_evolver_sessions(sessions):
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for s in sessions:
        path = BRIDGE_DIR / f"{s['id']}.json"
        path.write_text(json.dumps(s, indent=2))
        count += 1
    return count

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-sync", action="store_true", help="Sync all sessions instead of recent 50")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
    args = parser.parse_args()
    
    sessions = read_hermes_sessions(full_sync=args.full_sync)
    if args.dry_run:
        print(f"Would sync {len(sessions)} sessions to {BRIDGE_DIR}")
    else:
        count = write_evolver_sessions(sessions)
        print(f"Synced {count} sessions to {BRIDGE_DIR}")

if __name__ == "__main__":
    main()
```

Verify it's running: `ls -lt ~/.openclaw/agents/hermes-agent/sessions/ | head -5`

---

## Step 2: Evolver GEPA

**Location:** `~/.hermes/hermes-agent/hermes-agent-self-evolution/`

Key files:
- `assets/gep/events.jsonl` — EvolutionEvents (score, signal tags, capsule_id)
- `assets/gep/capsules.json` — Gene diffs awaiting approval
- `assets/gep/rtk_metrics.jsonl` — Per-session RTK scores
- `assets/gep/signals.json` — errsig detection results

### Validate Evolver Setup (Recommended)

```bash
cd ~/.hermes/hermes-agent/hermes-agent-self-evolution

# Node CLI (recommended)
node evolve.js --dry-run

# Or Python module / CLI
python3 -m evolver.cli validate-gepa \
  --scan-dir ~/.openclaw/agents/hermes-agent/sessions/ \
  --assets-dir assets/gep

# Dry-run via Python module
python3 -m dspy.evolve gepa_dry_run --config config/gepa.yaml
```

Expected: Report showing candidate prompts and RTK metric estimates.

### Run One Evolution Cycle

```bash
cd ~/.hermes/hermes-agent/hermes-agent-self-evolution

# Python CLI (recommended)
OPENAI_API_BASE=https://ark.cn-beijing.volces.com/api/coding/v3 \
OPENAI_API_KEY=your_ark_api_key \
python3 -m evolver.cli run-cycle \
  --scan-dir ~/.openclaw/agents/hermes-agent/sessions/ \
  --output-dir assets/gep \
  --model openai --model-name gpt-4o

# Alternative Node CLI
OPENAI_API_KEY=sk-... node evolve.js

# Alternative Python Module
python3 -m gep.evolve --skills skills/ --output evolved/
```

### Trigger Full Evolution Cycle (Continuous)

```bash
cd ~/.hermes/hermes-agent/hermes-agent-self-evolution
OPENAI_API_BASE=https://ark.cn-beijing.volces.com/api/coding/v3 \
OPENAI_API_KEY=your_ark_api_key \
python3 -m evolve_server --use-skillclaw-config --engine workflow --publish-mode direct --interval 300
```

Verify evolver output:
```bash
tail -5 ~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/events.jsonl
tail -5 ~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/capsules.json
```

---

## Step 3: Wire Evolution Results → SimpleMem Evolution Store

⚠️ **This step does not exist yet.** The evolver produces results but nothing reads them into SimpleMem.

The SimpleMem Evolution Store uses SQLite at `~/.hermes/simplemem_evolution/evolution.db`.

Schema:
```sql
CREATE TABLE evolution_entries (
    entry_id   TEXT PRIMARY KEY,
    weight     REAL NOT NULL DEFAULT 1.0,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed TEXT,
    created_at TEXT NOT NULL,
    decay_history TEXT NOT NULL DEFAULT '[]'
);
```

### Full Step 3 Implementation (Write This Script)

```python
#!/usr/bin/env python3
"""evolver_to_simplemem.py — Read events.jsonl, write to evolution.db"""
import sqlite3, json, sys
from datetime import datetime
from pathlib import Path

EVENTS = Path.home() / ".hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/events.jsonl"
DB = Path.home() / ".hermes/simplemem_evolution/evolution.db"
CHECKPOINT = Path.home() / ".hermes/simplemem_evolution/evolver_sync_checkpoint.json"

def load_checkpoint():
    """Read checkpoint — only process events newer than last_sync."""
    if CHECKPOINT.exists():
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {"last_event_id": None}

def save_checkpoint(last_event_id):
    with open(CHECKPOINT, "w") as f:
        json.dump({"last_event_id": last_event_id}, f)

def load_processed():
    """Get already-processed event IDs from the database."""
    conn = sqlite3.connect(DB)
    cur = conn.execute(
        "SELECT entry_id FROM evolution_entries WHERE entry_id LIKE 'evt_%'"
    )
    return {row[0] for row in cur.fetchall()}

def write_entry(conn, entry_id, signal_score, captured_at):
    conn.execute(
        """INSERT OR IGNORE INTO evolution_entries
           (entry_id, weight, access_count, last_accessed, created_at, decay_history)
           VALUES (?, ?, 0, NULL, ?, '[]')""",
        (entry_id, signal_score, captured_at)
    )

if not EVENTS.exists():
    print("No events.jsonl found, skipping Step 3")
    sys.exit(0)

checkpoint = load_checkpoint()
conn = sqlite3.connect(DB)
processed = load_processed()
count = 0
last_event_id = checkpoint.get("last_event_id")

with open(EVENTS) as f:
    for line in f:
        evt = json.loads(line)
        if evt.get("type") != "EvolutionEvent":
            continue
        if evt["id"] == last_event_id:
            break  # already processed
        if evt["id"] in processed:
            continue
        score = evt.get("outcome", {}).get("score", evt.get("signals", {}).get("overall_score", 1.0))
        captured_at = evt.get("captured_at", datetime.utcnow().isoformat())
        write_entry(conn, evt["id"], score, captured_at)
        last_event_id = evt["id"]
        count += 1

conn.commit()
conn.close()

if last_event_id:
    save_checkpoint(last_event_id)
print(f"Wrote {count} entries to evolution store")
```

Run this after each evolver cycle (append to cron job or run as separate job on a 30-min offset).

### GEPA Hooks — Design Reference (Not Yet Implemented)

| Hook | Purpose | Status |
|---|---|---|
| `gep_recall` | Hermes queries evolver for relevant past strategies | **Not implemented** |
| `gep_record_outcome` | Hermes reports session outcome back to evolver for learning | **Not implemented** |
| `finalize_and_decay` | Triggered after evolution cycle completes | **Not implemented** |
| `evolution_remember` | SimpleMem Evolution Store write via MCP | **Implemented** — writes to `evolution.db` directly via SQLite |

⚠️ **CRITICAL**: Do NOT call `gep_recall`, `gep_record_outcome`, or `finalize_and_decay` from the Hermes agent side — these functions are referenced in the skill documentation but are NOT implemented in the Hermes agent codebase. They exist only as placeholder names in the SKILL.md, not as actual callable functions. The only reliable write path is SQLite INSERT OR IGNORE directly.

### Gene Approval Workflow

After GEPA produces a capsule in `capsules.json`:
1. Capsule appears as PENDING in cron job output
2. Human reviews the diff (contained in `capsules.json`)
3. Approved capsules are written to `capsules.json` with `status: approved`
4. Step 3 script reads approved capsules and writes to Evolution Store

---

## Cron Job Management

### Method 1: Crontab
```bash
crontab -e
# Add:
*/15 * * * * cd ~/.hermes/hermes-agent/scripts && python3 hermes_to_evolver_bridge.py >> ~/.hermes/logs/bridge.log 2>&1
```
**Verify:** `crontab -l | grep bridge`

### Method 2: cronjob CLI
```bash
# List cron jobs
cronjob --list

# View next run for evolver bridge
cronjob --info 6cf04f3139de

# Manually trigger
cronjob --trigger 6cf04f3139de
```

**Cron schedule:** `0 */4 * * *` (every 4 hours). Last run visible at `~/.hermes/cron/output/6cf04f3139de/`.

### Adding Step 3 to Cron

1. Edit the cron job prompt to include running `evolver_to_simplemem.py` after Step 2.
2. Or add a separate cron job that runs `evolver_to_simplemem.py` every 4h on a 30-min offset from the bridge job.

---

## Expected Output Files

| Path | Contents |
|------|----------|
| `~/.openclaw/agents/hermes-agent/sessions/*.jsonl` | Session transcripts |
| `~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/rtk_metrics.jsonl` | Per-turn signal/quality metrics |
| `~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/events.jsonl` | EvolutionEvents + ValidationReports |
| `~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/capsules.json` | Gene diffs (PENDING/approved) |
| `~/.hermes/cron/output/6cf04f3139de/*.md` | Cron job reports |
| `~/.hermes/hermes-agent/hermes-agent-self-evolution/reports/` | Evolver cycle reports |

### View Cycle Output
```bash
ls -lt ~/.hermes/cron/output/6cf04f3139de/ | head -3
cat ~/.hermes/cron/output/6cf04f3139de/2026-*.md | tail -60
```

---

## SkillClaw Config Override Workaround

> ⚠️ **CRITICAL**: `_configure_hermes` in `claw_adapter.py` overwrites `~/.hermes/config.yaml` every time you run `hermes mcp add`, `hermes mcp remove`, `hermes config set`, or hermes-agent install/upgrade. If you need persistent config changes, apply them **after** SkillClaw runs.

**Restore custom settings:**
```bash
bash ~/.hermes/restore_hermes_config.sh

# Or manually restore:
# 1. Re-apply your custom provider config
# 2. Restart hermes-gateway
launchctl kickstart -k gui/$(id -u)/com.hermes.gateway
```

**Verify:** `python3 ~/.skillclaw/claw_adapter.py _check_hermes_config 2>/dev/null && echo "Config OK"`

---

## Verification Checklist

```bash
# 1. Bridge script exists
ls ~/.hermes/hermes-agent/scripts/hermes_to_evolver_bridge.py

# 2. Evolver process running
ps aux | grep evolve_server | grep -v grep

# 3. Sessions being synced
ls -lt ~/.openclaw/agents/hermes-agent/sessions/ | head -3

# 4. GEPA producing output
cat ~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/events.jsonl | tail -1 | python3 -c "import sys,json; e=json.load(sys.stdin); print(e.get('type'), e.get('id'))"

# 5. No GEPA hooks implemented (confirm known gap)
grep -r "gep_recall\|gep_record_outcome\|finalize_and_decay" ~/.hermes/hermes-agent/ 2>/dev/null | wc -l
# Expected: 0 — these functions don't exist yet

# 6. SimpleMem Evolution Store (Step 3 gap)
sqlite3 ~/.hermes/simplemem_evolution/evolution.db "SELECT COUNT(*) FROM evolution_entries;"
# Expected: 0 — Step 3 not built

# 7. Manual bridge run
cd ~/.hermes/hermes-agent && python3 scripts/hermes_to_evolver_bridge.py --dry-run
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bridge script not found at `~/.hermes/scripts/` | Correct path is `~/.hermes/hermes-agent/scripts/hermes_to_evolver_bridge.py` |
| Evolver API connectivity errors | Set `OPENAI_API_BASE` and `OPENAI_API_KEY` before running — see Network section |
| Sessions not syncing | Check `~/.openclaw/agents/hermes-agent/sessions/` — verify `OPENCLAW_AGENT_DIR` env var matches |
| TLS timeouts on MacBook | Use the ARK Volcengine endpoint documented above |
| Config resets after `hermes config set` or install | Apply changes after SkillClaw runs, or run `restore_hermes_config.sh` |
| SimpleMem evolution store empty | Step 3 bridge is not implemented — evolver output goes to files but not to SimpleMem |
| GEPA hooks (gep_recall, etc.) not working | These are placeholder names, not implemented functions — use SQLite directly |
| evolver server port 1935 returns 404 | Server is running but the `/api/stats` endpoint may not exist — check the actual FastMCP routes |

---

## Regression Testing

After any change, always run the full skill validation:
```bash
python3 /tmp/validate_skills.py --path ~/.hermes/skills/
```
Expected: "All checks passed." — 0 errors, 0 warnings across all skills.
