---
name: hermes-evolver-integration
description: "Integrate Hermes Agent with Evolver (NousResearch/hermes-agent-self-evolution) via lightweight bridge — sync Hermes session logs to Evolver's scan directory, run GEPA optimization dry-run to validate setup, and optionally trigger full evolution runs. ⚠️ CRITICAL: SkillClaw's `_configure_hermes` (claw_adapter.py) OVERWRITES `~/.hermes/config.yaml` on every `hermes mcp add`, `hermes config set`, or hermes-agent install/upgrade. To preserve manual edits, add them to `~/.hermes/config.yaml.d/` or re-apply after each install. NOT for: simple session recall (use SimpleMem MCP `memory_search` instead), non-Hermes agent evolver setups, or skill authoring without evolver."
category: general
---

## Architecture

Note: The bridge scripts were relocated from `~/.hermes/hermes-agent/scripts/` to `~/.hermes/` (repo root). All cron jobs reference the repo-root paths.

### Primary Data Flow (Paths A + E/F, Current Working Set)

```
WRITE PATH A: simplemem_memory_bridge.py (CRON */30) — PRIMARY WRITER (~90% of entries)
Hermes state.db ─→ simplemem_memory_bridge.py ─→ SimpleMem Evolution Store
(sessions table)                                    (evolution.db)

WRITE PATHS E+F: Dual-Path Bridge Architecture (Phase C, 2026-06-08)
See `references/evolution-bridge-dual-path.md` for full details.

Path E: evolver_to_simplemem.py (standalone script, cron/adhoc)
~/.hermes/hermes-agent-self-evolution/assets/gep/events.jsonl
    ↓ evolver_to_simplemem.py (checkpoint-based, max 100 events/run)
SimpleMem Evolution Store (~/.hermes/simplemem_evolution/evolution.db)

Path F: bridge_finalize_and_decay (MCP tool, runtime sync)
Hermes Agent Runtime (SimpleMemSystem.finalize())
    ↓ bridge_finalize_and_decay MCP tool (upsert + decay_all)
SimpleMem Evolution Store (~/.hermes/simplemem_evolution/evolution.db)
```

### Legacy (Broken/Inactive) Paths

```
WRITE PATH B: Runtime SessionEventLog — DORMANT (no longer writing)
WRITE PATH C: hermes_to_evolver_bridge + evolver_analysis.py — BROKEN
  (column mismatch in Step 1, script missing in Step 2)
WRITE PATH D: evolution-recorder plugin — MISSING (files never git-committed)
```

See `references/evolution-data-flow-topology.md` for the full six-path breakdown, and
`references/evolution-bridge-dual-path.md` for the dual-path architecture (Paths E+F).


**RTK (Runtime Kernel) metrics** track signal/quality scores over time, logged to:
`~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/rtk_metrics.jsonl`

Each line is a JSON object with: `timestamp`, `session_id`, `signal_score`, `quality_score`, `tokens_used`.

bash
tail -5 ~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/rtk_metrics.jsonl | jq


### Key Paths (Current Architecture — see `references/evolution-bridge-dual-path.md` and `references/evolution-data-flow-topology.md` for full write-path topology)

| Component | Path |
|-----------|------|
| Hermes state.db | `~/.hermes/state.db` |
| Evolver scan dir | `~/.openclaw/agents/hermes-agent/sessions/` |
| GEP output dir | `~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/` |
| Bridge script (Step 1) | `~/.hermes/hermes_to_evolver_bridge.py` |
| Step 2 (missing) | `~/.hermes/evolver_analysis.py` — **never committed, do not rely on** |
| Path E bridge script | `~/.hermes/evolver_to_simplemem.py` — standalone, checkpoint-based sync |
| Path F MCP tool | `bridge_finalize_and_decay` — in `simplemem_evolution_mcp.py` |
| SimpleMem Evolution DB | `~/.hermes/simplemem_evolution/evolution.db` |
| Cron job (Step 1 only) | "Hermes-Evolver Bridge + Analysis" (job_id: `6cf04f3139de`, every 4h — runs only Step 1) |
| Cron job (Path E) | Proposed — `evolver_to_simplemem.py` at `30 */4 * * *` (offset from bridge cron) |
| Hermes agent venv | `~/.hermes/hermes-agent/venv/bin/python3` (use this, NOT plain `python3`, for cron) |
| MCP server venv | `~/.hermes/mcp-venv/bin/python3` (for Evolution Store services/genes) |

### Local Hooks (Claude Code)

- `~/.claude/hooks/evolver-session-start.js` — runs before each Claude Code session
- `~/.claude/hooks/evolver-session-end.js` — records outcome after each session
- `~/.claude/hooks/evolver-signal-detect.js` — detects improvement opportunities

**Current status (2026-06-06, after deep investigation):**

⚠️ **The bridge pipeline has critical breakages that prevent it from functioning:**

- **Step 1 (`hermes_to_evolver_bridge.py`)** ❌ BROKEN — queries `state.db` with columns `session_id, started_at, ended_at, summary` but the actual schema uses `id, start_time, end_time, end_reason`. Column-name mismatch causes the SQL query to silently return 0 rows. Bridge always logs `"Found 0 sessions to process"`.
- **Step 2 (`evolver_analysis.py`)** ❌ MISSING — the script file does not exist at any documented location (`~/.hermes/evolver_analysis.py`, nor anywhere in the hermes-agent-self-evolution repo). It was likely a test script that was never committed, or was deleted during cleanup. Bridge logs show it ran at least once (generating 23 identical events), suggesting it was a one-time manual execution.
- **Step 3 (evolution.db persistence)** ❌ PARTIALLY WORKING — The evolution DB has 5018 entries, but these were written directly by the agent runtime (via `SessionEventLog`/`AIAgent` hooks), NOT by the bridge pipeline's analysis step.
- **Cron job** runs but achieves nothing — Step 1 finds 0 sessions, Step 2 script is absent.

**What IS working:**
- **`simplemem_memory_bridge.py` (cron */30)** is the **primary writer** to evolution.db — ~6577 entries in `YYYYMMDD_HHMMSS_-tool-*` format, dominating recent records. This is a separate write path from the evolver bridge, processing ended sessions with LLM importance extraction. See `references/evolution-data-flow-topology.md`.
- The agent runtime has **legacy evolution data collection** — `SessionEventLog` in `run_agent.py` records tool calls, session summaries, and turn-level metrics (3805 `tool_call_*` entries, 628 date-prefixed turn entries, 244 session summaries) — but this path appears inactive for recent sessions.
- The **SimpleMem decay scheduler** runs every 120s in the background, applying weight decay to evolution entries.
- The **CMA-ES engine** (6 files in `~/.hermes/hermes-agent-self-evolution/evolution/`) is fully written but never integrated with the bridge pipeline or the runtime agent.

**Key finding: Two disconnected evolution paths exist:**
1. **SimpleMem Evolution Store** ← Agent runtime writes tool_call + session data (write-only, no feedback to runtime)
2. **CMA-ES Engine** ← hermes-agent-self-evolution/evolution/ (optimization code exists, but no deployment mechanism)

Neither path closes the feedback loop to the running agent. Data accumulates but is never consumed for behavior modification.

**Known gaps (deep analysis findings):**
- `evolver_to_simplemem.py` — proposed as Step 3 but never needed; analysis script was supposed to handle this but was lost
- `evolver_analysis.py` — missing script; the cron pipeline cannot proceed without it
- Bridge column-name mismatch blocks Step 1 — fix requires updating SQL to match state.db's actual schema
- All 23 events in `events.jsonl` are identical (same signals, same score=0.985) — the script that ran once analyzed the same dataset repeatedly
- Gene system (~7 pattern-trigger genes, as optimized 2026-06-08) has `usage_count: 0` on all genes — `run_agent.py` never calls `GeneStore.match()`

---

## Prerequisites

### Network: ARK Volcengine Endpoint (NOT `api.openai.com`)

If `api.openai.com` is unreachable (TLS timeout), set `OPENAI_API_BASE` and `OPENAI_API_KEY` in `~/.hermes/hermes-agent/.env`:

bash
echo 'OPENAI_API_BASE=https://ark.cn-beijing.volces.com/api/coding/v3' >> ~/.hermes/hermes-agent/.env
echo 'OPENAI_API_KEY=your-ark-api-key' >> ~/.hermes/hermes-agent/.env


The `evolve.js` Node CLI hardcodes `api.openai.com`, but `dotenv` loads `OPENAI_API_BASE` at startup, overriding the hardcoded value before any HTTP calls are made. No JavaScript patching required.

**Verify connectivity:**
bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer <your-ark-key>" \
  https://ark.cn-beijing.volces.com/api/coding/v3/models

Expected: `200`

### Platform: Use venv python3, NOT plain `python3`

On MacBooks, the default `python3` command may work interactively but cron jobs have a minimal PATH. Always use the full venv path in cron commands:

```bash
# Correct — use in cron scripts
~/.hermes/hermes-agent/venv/bin/python3 ~/.hermes/hermes_to_evolver_bridge.py

# The cron delivery requires absolute paths; symlinks in ~/.hermes/scripts/ are resolved to real paths by the scheduler
```

---

## Quick Start

### 1. Verify Prerequisites

```bash
# Check bridge script exists (repo root)
ls ~/.hermes/hermes_to_evolver_bridge.py

# Check analysis script exists (repo root)
ls ~/.hermes/evolver_analysis.py

# Check sessions are syncing
ls ~/.openclaw/agents/hermes-agent/sessions/ | wc -l  # should be > 0

# Check Evolution Store populated
sqlite3 ~/.hermes/simplemem_evolution/evolution.db "SELECT COUNT(*) FROM evolution_entries;"
```

### 2. Run Bridge Manually

bash
cd ~/.hermes/hermes-agent/hermes-agent-self-evolution
OPENAI_API_BASE=https://ark.cn-beijing.volces.com/api/coding/v3 \
OPENAI_API_KEY=your_ark_api_key \
python3 scripts/hermes_to_evolver_bridge.py --full-sync


### 3. Verify Scan Directory

bash
ls ~/.openclaw/agents/hermes-agent/sessions/ | head


---

## Step 1: Bridge Script

**Location:** `~/.hermes/hermes-agent/scripts/hermes_to_evolver_bridge.py`

The bridge syncs Hermes session logs from `~/.hermes/state.db` → `~/.openclaw/agents/hermes-agent/sessions/` (Evolver's scan directory).

python
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


Verify it's running: `ls -lt ~/.openclaw/agents/hermes-agent/sessions/ | head -5`

---

## Step 2: evolver_analysis.py (Cron Analysis Pipeline)

**Location:** `~/.hermes/evolver_analysis.py`

This standalone Python script is the current Step 2 of the cron pipeline. It:
1. Loads RTK metrics from `~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/rtk_metrics.jsonl`
2. Detects evolution signals (low_engagement, context_bloat, skill_drift, errsig)
3. Creates an EvolutionEvent with signal scores and outcome metrics
4. Writes the event to `signals.json` and appends to `events.jsonl` in the GEP directory
5. Persists the event to `~/.hermes/simplemem_evolution/evolution.db` directly (combining legacy Steps 2+3)

**Run manually:**
```bash
~/.hermes/hermes-agent/venv/bin/python3 ~/.hermes/evolver_analysis.py
```

**Key files consumed/produced:**
- Input: `GEP_DIR/rtk_metrics.jsonl` (at `hermes-agent-self-evolution/assets/gep/`)
- Output: `GEP_DIR/signals.json`, `GEP_DIR/events.jsonl`
- Side-effect: INSERT INTO `~/.hermes/simplemem_evolution/evolution.db`

**Detected signal types:**
- `errsig` — error rate > 2% threshold
- `low_engagement` — active ratio < 50%
- `context_bloat` — tokens per session > 100K threshold
- `skill_drift` — skill usage changes > 20% since baseline

### Validate Evolver Setup (Recommended)

bash
cd ~/.hermes/hermes-agent/hermes-agent-self-evolution

# Node CLI (recommended)
node evolve.js --dry-run

# Or Python module / CLI
python3 -m evolver.cli validate-gepa \
  --scan-dir ~/.openclaw/agents/hermes-agent/sessions/ \
  --assets-dir assets/gep

# Dry-run via Python module
python3 -m dspy.evolve gepa_dry_run --config config/gepa.yaml


Expected: Report showing candidate prompts and RTK metric estimates.

### Run One Evolution Cycle

bash
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


### Trigger Full Evolution Cycle (Continuous)

bash
cd ~/.hermes/hermes-agent/hermes-agent-self-evolution
OPENAI_API_BASE=https://ark.cn-beijing.volces.com/api/coding/v3 \
OPENAI_API_KEY=your_ark_api_key \
python3 -m evolve_server --use-skillclaw-config --engine workflow --publish-mode direct --interval 300


Verify evolver output:
bash
tail -5 ~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/events.jsonl
tail -5 ~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/capsules.json


---

## Step 3: Evolution Store Persistence (Dual-Path Bridge)

**evolver_analysis.py is MISSING and NOT the current Step 3.** Two working paths persist data to evolution.db:

**Path E — Standalone Script (`evolver_to_simplemem.py`):**
Batch-syncs evolver analysis output (events.jsonl) to the evolution store.
- **File:** `~/.hermes/evolver_to_simplemem.py`
- **Source:** `~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/events.jsonl`
- **Mechanism:** Reads events from checkpointed line offset, writes via direct SQLite (INSERT OR IGNORE)
- **Invocation:** `~/.hermes/hermes-agent/venv/bin/python3 ~/.hermes/evolver_to_simplemem.py`
- **Idempotent:** Tracks last-processed line number via checkpoint file
- **Max batch:** 100 events per run

**Path F — MCP Tool (`bridge_finalize_and_decay`):**
Real-time sync from Hermes Agent runtime after `SimpleMemSystem.finalize()`.
- **Exposed by:** `simplemem_evolution_mcp.py` (MCP server)
- **Behavior:** Receives JSON list of entry_ids → upsert into evolution.db → trigger decay_all()
- **Returns:** `{registered_count, decayed_count, forgotten_count}`

Both paths write to the **same schema:**
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

### Verify with:

```bash
# Check entry count
sqlite3 ~/.hermes/simplemem_evolution/evolution.db "SELECT COUNT(*) FROM evolution_entries;"

# Check write path breakdown by entry_id prefix
sqlite3 ~/.hermes/simplemem_evolution/evolution.db \
  "SELECT substr(entry_id,1,15) AS prefix, COUNT(*) FROM evolution_entries GROUP BY prefix ORDER BY COUNT(*) DESC LIMIT 10;"
```

### Gene Approval Workflow (Legacy)

The old GEPA pipeline produced capsules in `capsules.json` for human review. The current pipeline (Path E) skips this — events are synced directly. If capsule-based approval is needed, the old `hermes-agent-self-evolution` repo's GEPA tools can be run independently.

For the full dual-path architecture comparison, see `references/evolution-bridge-dual-path.md`.

---

## Cron Job Management

### Method 1: Crontab

bash
crontab -e
# Add:
*/15 * * * * cd ~/.hermes/hermes-agent/scripts && python3 hermes_to_evolver_bridge.py >> ~/.hermes/logs/bridge.log 2>&1


**Verify:**
bash
crontab -l | grep bridge


### Method 2: cronjob CLI

bash
# List cron jobs
cronjob --list

# View next run for evolver bridge
cronjob --info 6cf04f3139de

# Manually trigger
cronjob --trigger 6cf04f3139de


**Cron schedule:** `0 */4 * * *` (every 4 hours). Last run visible at `~/.hermes/cron/output/6cf04f3139de/`.

### Adding Path E (evolver_to_simplemem.py) to Cron

```bash
cronjob --schedule "30 */4 * * *" \
  --prompt "Run evolver_to_simplemem.py to sync events.jsonl to evolution.db" \
  --script ~/.hermes/evolver_to_simplemem.py
```

This runs 30 min after the Hermes-Evolver Bridge cron (which fires at `0 */4 * * *`), allowing the bridge pipeline time to produce new events.

Or add as a fallback in the bridge cron's prompt: add `~/.hermes/hermes-agent/venv/bin/python3 ~/.hermes/evolver_to_simplemem.py` to the end of the existing cron job's prompt.

---

## Expected Output Files

| Path | Contents |
|------|----------|
| `~/.openclaw/agents/hermes-agent/sessions/*.jsonl` | Session transcripts (written by bridge) |
| `~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/rtk_metrics.jsonl` | Per-turn signal/quality metrics |
| `~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/events.jsonl` | EvolutionEvents (written by analysis) |
| `~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/signals.json` | Detected signals + summary (written by analysis) |
| `~/.hermes/cron/output/6cf04f3139de/*.md` | Cron job reports |
| `~/.hermes/simplemem_evolution/evolution.db` | Persistent EvolutionEvent store (two concurrent write paths: simplemem_memory_bridge.py cron + evolver_to_simplemem.py) |
| `~/.hermes/evolver_bridge_checkpoint.txt` | Checkpoint file for Path E incremental sync |

### View Cycle Output

bash
# Latest cron output
ls -lt ~/.hermes/cron/output/6cf04f3139de/ | head -3
cat ~/.hermes/cron/output/6cf04f3139de/2026-*.md | tail -60


---

---

## Skill Evolution Pipeline (MIPROv2 — Replaces CMA-ES Engine)

⚠️ **The old CMA-ES/GEPA engine described in `references/cma-es-engine-analysis.md` has been replaced.** The actual running pipeline (cron job `self-evolution-cycle`, id `8a91ef5593a1`) now uses **DSPy MIPROv2 optimizer** via `evolution/skills/evolve_skill.py`, launched through `run-evolution.sh` → `python -m evolution.skills.evolve_skill`.

**Unlike the old documented state, the current pipeline DOES have a deployment mechanism** — at line ~310 of `evolve_skill.py`:

```python
if improvement > 0:
    skill_path.write_text(evolved_full)
else:
    log("⚠ 技能未改善 — 不部署")
```

However, this gate is **insufficient** — see the deployment pitfalls below.

### Current Deployment Pitfalls

| Issue | Detail | Impact |
|-------|--------|--------|
| **Content collapse** | MIPROv2 with small eval datasets (10 train, 5 val, 5 holdout) often produces drastically shortened skills: 3060→211 chars, 7145→947 chars | Most "evolved" skills lose all substantive content |
| **Weak deployment gate** | `improvement > 0` doesn't catch content collapse — a skill can score 0.300→0.301 while losing 95% of content | Two skills per cycle fail deployment (improvement ≤ 0), but many that pass are degenerated |
| **Score floor at 0.300** | Several skills (anfu-skill, threat-intel, vuln-assessment) stuck at exactly 0.300 — indicates eval data is too sparse to produce meaningful scores | Optimizer has no gradient signal for large/domain-heavy skills |
| **Small eval datasets** | 10 train + 5 val + 5 holdout = too few examples for MIPROv2 to generalize | Optimizer overfits to trivial patterns; content degenerates |

### Fixes to Apply

**Urgent (size sanity gate):** Add a content-size ratio check to the deploy gate:
```python
size_ratio = len(evolved_full) / len(original_content)
if improvement > 0 and size_ratio > 0.3:  # reject >70% content loss
    skill_path.write_text(evolved_full)
elif size_ratio <= 0.3:
    log("⚠ 内容坍塌 — 不部署 (ratio={:.2f})".format(size_ratio))
```

**Medium-term:** Expand eval datasets to ≥50 samples per skill. Without sufficient evaluation data, MIPROv2 cannot meaningfully optimize large domain-specific skills.

### Metrics from Latest Cycle

See `references/miprov2-deployment-analysis.md` for the full metrics from the most recent self-evolution cycle (2026-06-07, 22 skills evolved, 2 blocked, ~20 deployed but content-collapsed).

### Engine Files

| File | Path | Purpose | Size |
|------|------|---------|------|
| `skills/evolve_skill.py` | `evolution/skills/evolve_skill.py` | **Active:** MIPROv2 optimization loop (replaces old GEPA). Deploys to `~/.hermes/skills/` if improvement > 0. | 17.6 KB |
| `skills/skill_module.py` | `evolution/skills/skill_module.py` | Skill module abstraction layer | 5.7 KB |
| `core/config.py` | `evolution/core/config.py` | Engine hyperparams (population, mutation, crossover) | 2.6 KB |
| `core/fitness.py` | `evolution/core/fitness.py` | Fitness evaluation for skill quality | 6.5 KB |
| `core/constraints.py` | `evolution/core/constraints.py` | Skill constraints and validation | 7.2 KB |
| `core/dataset_builder.py` | `evolution/core/dataset_builder.py` | Training dataset from sessions | 4.2 KB |

### What the Engine Does

1. **Loads** session data from the Evolver scan directory (`~/.openclaw/agents/hermes-agent/sessions/`)
2. **Builds** a training dataset using `dataset_builder.py`
3. **Evaluates** skill fitness using `fitness.py` with constraints from `constraints.py`
4. **Evolves** skill parameters via CMA-ES (DSPy GEPA) in `evolve_skill.py`
5. **Outputs** evolved skill candidates

### ⚠️ Status: Replaced by MIPROv2 Pipeline

**As of 2026-06-07, the CMA-ES/GEPA engine is no longer the active evolution pipeline.** The cron job `self-evolution-cycle` (id `8a91ef5593a1`) now uses `evolution/skills/evolve_skill.py` with DSPy MIPROv2, launched through `run-evolution.sh`. See the "Skill Evolution Pipeline (MIPROv2)" section above for the current system.

The old CMA-ES/GEPA engine (detailed in `references/cma-es-engine-analysis.md`) had:
- **CMA-ES population-based optimization** (population 20, generations 10)
- **GEPA module** for fitness-guided mutation
- **No deployment mechanism** — candidates were written to the GEP assets dir but never pushed to `~/.hermes/skills/`
- **No cron integration** — had to be run manually
- **Input starvation** — `dataset_builder.py` read from sessions/ dir produced by the broken bridge Step 1

The MIPROv2 replacement fixes the deployment gap (has a working gate) but introduces new issues — see the deployment pitfalls above.

### Integration Gap (Historical)

Before the MIPROv2 pipeline, the old CMA-ES engine and the SimpleMem evolution store were completely disconnected:

```
SimpleMem Evolution (5018 entries)                          CMA-ES Engine (6 files)
    ↓ stores tool_call + session data                           ↓ uses DSPy GEPA
    ↓ NO feedback to runtime                                    ↓ NO deployment to skills
    └─── write-only, no consumer                                └─── optimize-only, no publisher
```

This gap was partially closed by the MIPROv2 pipeline (it reads skills and writes back to `~/.hermes/skills/`), but the evolution store data is still not consumed for runtime behavior modification.

---

## Gene System (SimpleMem Genes)

**File:** `~/.hermes/simplemem_evolution/genes.json`
**Entity Type:** Trigger-action rules for adaptive behavior

### Trigger & Action Types

**Trigger types** (defined in `GeneTrigger` class):
| Type | Behavior | Example |
|------|----------|---------|
| `keyword` | Case-insensitive substring match in context string | `"session_end"` matches any context containing `session_end` |
| `pattern` | Compiled regex (case-insensitive with `(?i)`) | `"(?i)\\bsession[ _-]?end\\b"` matches `session_end`, `Session end`, `session-end` |
| `error` | Matches error-type contexts | `"tool_error"` |
| `action` | Matches specific action context | `"memorize"` |

**Action types** (validated server-side):
| Type | Behavior |
|------|----------|
| `remember` | Store a fact in the evolution store |
| `suggest` | Return a suggestion text for context injection |
| `script` | Execute a script (by name/path) |

⚠️ **Only these 3 action types are valid.** Passing any other type (e.g. `reduce_weight`, `boost_weight`) causes `GeneAction` validation to log errors and silently ignore the action.

### Current Genes (~7 pattern-trigger genes, as of 2026-06-08)

| Gene ID | Trigger Patterns | Purpose |
|---------|-----------------|---------|
| `ctx_session_end` | `\\bsession[ _-]?end\\b`, 会话结束, compaction | Consolidate session decisions on end |
| `decay_tool_output_noise` | `tool.*output`, terminal noise, tool noise | Reduce weight of noisy tool output |
| `boost_user_profile` | My name is, i am, my role is, 用户信息, 我叫 | Boost user-identity memories |
| `pattern_phase_tracking` | phase/stage/step/iteration N | Track multi-phase progress |
| `err_secret_guard` | api_key, sk-, secret, token, password, 密钥, 密码 | Flag potential secret leaks |
| `boost_security_operations` | cve, cvss, 漏洞, security, incident, 应急, 威胁 | Prioritize security-related memories |
| `ctx_config_validation` | config, setting, setup, configure, init, 初始化, 配置 | Validate config-related context |

### Local Testing (Without MCP Server)

The MCP server caches `genes.json` in memory at startup. To test gene changes before restarting:

```bash
cd ~/.hermes/simplemem_evolution

# Use MCP venv (has pydantic installed)
MCP_PYTHON=/Users/can/.hermes/mcp-venv/bin/python3

# Quick: load genes and count
$MCP_PYTHON -c "
from gene_store import GeneStore
store = GeneStore()
print(f'Loaded {len(store._genes)} genes')
print(f'Gene IDs: {[g.gene_id for g in store._genes]}')
"

# Test pattern matching against specific contexts
$MCP_PYTHON -c "
from gene_store import GeneStore
store = GeneStore()

contexts = [
    'session_end',
    '会话结束',
    'compaction notice',
    'tool terminal output noisy',
    'my name is can',
    'phase 1 completed',
    'api_key=sk-xxx',
    'cve-2024-1234',
    'config.yaml',
    'random text',
]
for ctx in contexts:
    match = store.match(ctx)
    result = match.gene_id if match else '(no match)'
    print(f'{ctx:>30s} \u2192 {result}')
"
```

`GeneStore.match(context)` returns **`Optional[Gene]`** (a single Gene object, **not** a list). Do not iterate the return value.

### Restarting MCP Server After Gene Changes

The MCP server loads `genes.json` once at startup and caches it. After writing a new `genes.json`:

1. **Check the MCP server definition** `~/.hermes/config.yaml` — look for `simplemem_evolution` in `mcp.servers:` (typically cwd = `simplemem_evolution/`, args = `[simplemem_evolution_mcp.py]`)
2. **Kill the subprocess** — the Hermes gateway auto-restarts stdio MCP servers. Killing the python subprocess causes the gateway to respawn it, loading the new config
3. **Verify** → call `mcp_simplemem_evolution_gene_list` — should show the updated gene IDs
4. **Verify matching** → call `mcp_simplemem_evolution_gene_match(context="session_end")` — should return the expected gene

### Root Cause of Zero Gene Usage

`run_agent.py` runtime **never calls `GeneStore.match()`** in its execution path. The gene matching logic exists in `gene_store.py` but there's no integration point:

- No hook in the conversation loop (`run_conversation()`)
- No hook in the tool execution pipeline (`handle_function_call()`)
- No hook in the session start/end lifecycle
- The `AIAgent` constructor does not load or reference `GeneStore`

Genes were designed for a future integration that was never built. To activate them, you would need to add a gene matching call at one of these points in `run_agent.py`:
- After `handle_function_call()` returns a tool error
- Before sending the LLM request in the conversation loop
- In `chat()` or `run_conversation()` as a context enrichment step

---

## Evolution DB Entry Categories (Deep Analysis)

Full analysis at `references/evolution-db-deep-analysis.md` (5018 entries as of 2026-06-04).
**🔔 Updated topology at `references/evolution-data-flow-topology.md` — 7314 entries as of 2026-06-07 with corrected write-path analysis (two concurrent data sources + new entry_id patterns).**

Legacy (5018-entry) category breakdown:

| Category | Pattern | Count | Avg Weight | Meaning |
|----------|---------|-------|------------|---------|
| Tool calls | `tool_call_*` | 3805 | 0.683 | Per-call records: function name, args, result summary |
| Cron sessions | `session_cron_*` | 251 | 0.766 | Cron job summaries: success rate, errors, duration |
| Turn meta | `YYYYMMDD_*` | 628 | 0.328 | Turn-level markers: user→end, tool→terminal, response |
| User sessions | `session-YYYYMMDD_*` | 244 | 0.493 | User session summaries: topic, message count |
| EvolutionEvents | `evt_*` | 79 | 0.358 | Cron analysis events (all identical — 23 in events.jsonl) |

### Key Observations

1. **Two write paths, one store** — Two independent processes (`simplemem_memory_bridge.py` and legacy `SessionEventLog`) write to the same DB with incompatible entry_id formats and different weight strategies. See `references/evolution-data-flow-topology.md`.
2. **Stale decay** — Entries decay to weight 0.1 floor but are never pruned (no threshold-based deletion; DECAY_FACTOR=0.02 as of Phase C)
3. **Identical events** — All 23 `evt_*` events have the same `signal_score: 0.985` and same signal types — indicates `evolver_analysis.py` (when it ran) analyzed the same snapshot repeatedly
4. **Heavy tool_call bias** — 75% of all entries are tool-level; no higher-level behavior patterns are derived

### Decay Scheduler Details

- Runs every 120s in the background (`decay_scheduler.py` started at `AIAgent.__init__`)
- Weight decay: `weight *= 0.9` per cycle for low-importance entries
- Floor at 0.1 — entries are never fully deleted
- Entry-type-based importance: `tool_call=high`, `session=medium`, `event=low`
- Problem: v1 events (from early April) get stuck at 0.1, each decay cycle records another `decay_history` entry at 0.1→0.1 (no-op)

---

## SkillClaw Config Override Workaround

> ⚠️ **CRITICAL**: `_configure_hermes` in `claw_adapter.py` overwrites `~/.hermes/config.yaml` every time you run `hermes mcp add`, `hermes mcp remove`, `hermes config set`, or hermes-agent install/upgrade. If you need persistent config changes, apply them **after** SkillClaw runs.

**Restore custom settings:**
bash
# Run restore script (recommended)
bash ~/.hermes/restore_hermes_config.sh

# Or manually restore:
# 1. Re-apply your custom provider config
# 2. Restart hermes-gateway
launchctl kickstart -k gui/$(id -u)/com.hermes.gateway


**Verify:**
bash
python3 ~/.skillclaw/claw_adapter.py _check_hermes_config 2>/dev/null && echo "Config OK"


---

## Verification Checklist

```bash
# 1. Bridge script exists
ls ~/.hermes/hermes-agent/scripts/hermes_to_evolver_bridge.py

# 2. Check state.db actual schema (compare vs bridge column names)
sqlite3 ~/.hermes/state.db ".schema sessions" | head -5

# 3. Run bridge with verbose output to confirm column mismatch
~/.hermes/hermes-agent/venv/bin/python3 ~/.hermes/hermes_to_evolver_bridge.py --dry-run 2>&1

# 4. Check if evolver_analysis.py exists (likely missing)
ls -la ~/.hermes/evolver_analysis.py 2>&1

# 5. Check evolution DB population
sqlite3 ~/.hermes/simplemem_evolution/evolution.db "SELECT COUNT(*) FROM evolution_entries;"
sqlite3 ~/.hermes/simplemem_evolution/evolution.db "SELECT substr(entry_id,1,10) AS prefix, COUNT(*) FROM evolution_entries GROUP BY prefix ORDER BY COUNT(*) DESC LIMIT 10;"

# 6. Check gene status (all should show usage_count=0)
cat ~/.hermes/simplemem_evolution/genes.json | python3 -c "import sys,json; data=json.load(sys.stdin); genes=data if isinstance(data,list) else data.get('genes',[]); [print(g['gene_id'], g['usage_count']) for g in genes[:5]]"

# 7. Check CMA-ES engine exists
ls ~/.hermes/hermes-agent-self-evolution/evolution/core/*.py
ls ~/.hermes/hermes-agent-self-evolution/evolution/skills/*.py

# 8. Verify cron job output (should show empty syncs)
ls -lt ~/.hermes/cron/output/6cf04f3139de/ 2>/dev/null | head -3
cat ~/.hermes/cron/output/6cf04f3139de/*.md 2>/dev/null | tail -30

# 9. Check events.jsonl for signal diversity
cat ~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/events.jsonl 2>/dev/null | \
  python3 -c "import sys,json; lines=[json.loads(l) for l in sys.stdin]; print(f'Events: {len(lines)}, Unique types: {len(set(e.get(\"type\",\"\") for e in lines))}, Signals: {[e.get(\"signals\",[]) for e in lines[:3]]}')"

# 10. Check RKT metrics file
wc -l ~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/rtk_metrics.jsonl 2>/dev/null
tail -1 ~/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/rtk_metrics.jsonl 2>/dev/null


---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bridge script not found at `~/.hermes/scripts/` | Correct path is `~/.hermes/hermes_to_evolver_bridge.py` (repo root). Also NOT at `~/.hermes/hermes-agent/scripts/` as older docs claimed. |
| Analysis script not found | `~/.hermes/evolver_analysis.py` **does not exist** — it was never committed to disk or was deleted. The cron pipeline cannot analyze sessions without it. |
| **Step 1 bridge finds 0 sessions** | Column name mismatch: bridge queries `session_id, started_at, ended_at, summary` but `state.db` uses `id, start_time, end_time, end_reason`. Fix the SQL in `hermes_to_evolver_bridge.py`. |
| **Step 2 script missing** | `evolver_analysis.py` was never committed. For Evolution Store persistence, use Path E (`evolver_to_simplemem.py`) or Path F (`bridge_finalize_and_decay` MCP tool) instead — see Step 3 section above. |
| **Evolver API connectivity errors** | Set `OPENAI_API_BASE` and `OPENAI_API_KEY` before running — see Network section |
| Sessions not syncing | Check `~/.openclaw/agents/hermes-agent/sessions/` — even after fixing the column names, verify that the bridge is writing `.json` files there |
| **TLS timeouts on MacBook** | Use the ARK Volcengine endpoint documented above |
| Config resets after `hermes config set` or install | Apply changes after SkillClaw runs, or run `restore_hermes_config.sh` |
| **Evolution DB has 7300+ entries but nothing uses them** | Two write paths (bridge cron */30 + legacy runtime) both INSERT into `evolution.db` but nothing SELECTs for runtime behavior modification. See `references/evolution-data-flow-topology.md` for the full topology and write-path breakdown. To close the loop: add a consumer that reads evolution entries and adjusts runtime behavior (e.g., tool selection, retry strategy, skill priority). |
| **Genes never fire** | `run_agent.py` doesn't call `GeneStore.match()`. Add a gene-matching call in the conversation loop or tool execution pipeline. |
| **Gene changes not reflected via MCP** | The MCP server caches `genes.json` in memory at startup. Writing a new `genes.json` has no effect until the server process is killed (gateway auto-restarts it). Kill the `simplemem_evolution_mcp.py` subprocess, then verify with `gene_list` / `gene_match` MCP tools. |
| **CMA-ES engine doesn't produce usable output** | ⚠️ **OUTDATED**: The CMA-ES engine has been replaced by the MIPROv2 pipeline. The MIPROv2 pipeline does deploy (writes to `~/.hermes/skills/`) but suffers from content collapse due to small eval datasets — see the Skill Evolution Pipeline section above. |
| **Decay events stuck at weight=0.1** | Add a pruning threshold (e.g., delete entries that have been at floor for >30 days). The current scheduler decays to 0.1 then recurses infinitely. |
| **All events.jsonl entries are identical** | `evolver_analysis.py` (when it ran) didn't track what it already processed. Any fix should include idempotency — track last-analyzed session ID and skip already-processed data. |
| Cron job fails with "python: command not found" | Use full path: `~/.hermes/hermes-agent/venv/bin/python3` — plain `python3` may not be in the cron PATH |
| GEPA hooks (gep_recall, etc.) not working | These were placeholder names from the old architecture. The current Python pipeline (hermes_to_evolver_bridge.py + evolver_analysis.py) replaces them entirely. |
| evolver server port 1935 returns 404 | Server is running but the `/api/stats` endpoint may not exist — check the actual FastMCP routes |

---

## Regression Testing

After any change, always run the full skill validation:

bash
python3 /tmp/validate_skills.py --path ~/.hermes/skills/


Expected: "All checks passed." — 0 errors, 0 warnings across all skills.
