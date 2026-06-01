|---
|name: pokemon-player
|description: "Use when playing Pokemon games autonomously via headless emulation. Starts a game server, reads structured game state from RAM, makes strategic decisions, and sends button inputs — all from the terminal. NOT for: non-Pokemon games, other game emulation, competitive online battles, real-time gaming, or when visual feedback is required."
|category: general
|---

## Architecture

- **pyboy** — pure Python Game Boy emulator; run headless (`--disable-render`)
- **Lua scripts** — embedded in save state; read/write RAM, push button combos
- **game-server.py** — Flask API wrapping pyboy + Lua bridge; exposes RAM addresses as REST endpoints
- **strategy/** — decision engine (type advantages, move priority, HP thresholds)
- **button_inputs/** — pre-built combo sequences (grinding, shiny hunting, etc.)

## Use when

- Playing Pokemon games automatically
- Training Pokemon for battle strategies
- Completing in-game tasks and quests
- Mass catching or farming Pokemon
- Testing game logic and mechanics
- Running Pokemon game automation on servers

## Startup

bash
# 1. Start game server
cd ~/.hermes/pokemon-player
python game-server.py --rom PokemonRed.gb --port 5000 &

# 2. Verify server is up
curl http://localhost:5000/health  # should return {"status": "ok", "state": "playing"}

# 3. Check RAM is readable
curl http://localhost:5000/ram?addr=0xC000  # HP of first party Pokemon


## RAM Map (Pokemon Red/Blue)

| Address | Size | Description |
|---------|------|-------------|
| 0xC000–0xC04F | 80 | Party Pokemon (6 × 44 bytes each) |
| 0xD058 | 1 | Current HP (low byte) |
| 0xD059 | 1 | Current HP (high byte) |
| 0xD016 | 1 | Current menu/overworld state |
| 0xD05E | 1 | Battle state (0=none, 1=enemy appeared, 2=battle) |
| 0xCC4B | 1 | Badge flags |
| 0xD721 | 1 | Pokemon caught flag |

## Key Endpoints

- `GET /ram?addr=0xXXXX` — read raw RAM at hex address
- `GET /party` — parse all 6 Pokemon: species, level, HP, status
- `GET /battle` — current battle state, enemy Pokemon, available moves
- `POST /button` — send a button press: `{"button": "A"}`, `{"button": "START"}`, etc.
- `POST /combo` — send a sequence: `{"sequence": ["LEFT", "A", "DOWN", 0.1, ...]}` (timestamps in seconds)
- `POST /save?name=mysave.state` — persist emulator state
- `GET /health` — health check

## Usage

bash
# Basic gameplay
curl -X POST http://localhost:5000/button -d '{"button":"A"}'

# Grind XP for 5 minutes (battles, then run)
curl -X POST http://localhost:5000/combo -d '{"sequence":["A",0.5,"LEFT",0.3,"A",0.5,"B",0.1],"loop":120}'

# Check party status
curl http://localhost:5000/party | jq '.[] | {species, level, hp}'

# Save progress
curl -X POST http://localhost:5000/save -d '{"name":"route1"}'

# Load saved state
curl -X POST http://localhost:5000/load -d '{"name":"route1"}'


## Batch File Modification Lessons (from skill evolution sessions)

When performing batch modifications to skill files (SKILL.md, JSON configs, YAML frontmatter), the following patterns were validated across 6+ agent sessions:

### 1. Always Verify Immediately with read_file, Not search_files

The patch tool may report `{"success": true}` even when changes don't persist to disk. Always read the file back immediately after patching to confirm:

bash
# WRONG: Trust patch success response
patch ... && echo "done"  # patch says OK but file unchanged

# RIGHT: Immediately read back to verify
patch ...
read_file(path, limit=5)  # confirm new content is actually there


### 2. Multiline YAML Block Scalars Need Careful Handling

Descriptions using `>`, `>-`, or `|` YAML multiline syntax are collapsed to single-line strings when patched. This changes the character count and can cause truncation. Always read the full multiline block first, then patch using the exact original string:

yaml
# BEFORE (multiline block scalar)
description: >
  Description text that
  spans multiple lines.

# AFTER (single-line string)
description: "Description text that spans multiple lines."


### 3. Patch Tool May Report Success Without Persisting

Across sessions, the patch tool returned `success: true` with valid diffs but the filesystem was not updated. When this happens:
- Re-read the file to see the current state
- Apply the patch again with the exact current string (not the string from before the failed patch)
- If a third attempt fails, consider using `terminal` with `sed` or direct file write

### 4. Batch Sizing: 5 Files Per Round is Optimal

Sessions that attempted larger batches (10-20 files) had higher failure rates due to:
- Stale context between reads and patches
- Cumulative string-matching drift
- No mid-batch verification

Optimal pattern:


read_file batch (5 files)
 ↓
patch batch (5 files)
 ↓
verify batch (5 files)
 ↓
repeat


### 5. search_files Caching vs. read_file Freshness

`search_files` may return cached/stale results showing new content that `read_file` doesn't yet show. Always use `read_file` as the source of truth for verification. Use `search_files` only for initial discovery (e.g., "which files contain this pattern").

## Purpose

To give an AI agent the ability to play Pokémon Game Boy titles (Red, Blue, Yellow, Crystal, etc.) entirely via headless emulation. The agent reads structured game state from emulator RAM, uses a decision engine for battle/movement strategy, and sends button input sequences through a REST API — no screen capture or human-in-the-loop required. This turns turn-based RPG gameplay into a programmable, scriptable automation task suitable for server environments.

## Why This Works

**Concept 1: RAM-as-API.** Rather than parsing pixels or OCR-ing a screen, the skill exposes emulator RAM addresses (party HP, battle state, menu position, badge flags) as structured JSON endpoints. The agent can make deterministic, low-latency decisions based on exact game state — no vision model, no screenshot latency.

**Concept 2: Combo Sequences as Macro Primitives.** Button presses are composed into parameterized sequences (e.g., `["A", 0.5, "LEFT", 0.3, "A"]`) that can be looped. This lets the agent execute multi-step grinding, catching, or movement routines as single atomic calls, reducing round-trips and API overhead.

**Concept 3: Save-State Checkpointing.** The emulator saves and loads full game state snapshots via `POST /save` / `POST /load`. This allows the agent to checkpoint before risky battles, retry failed encounters, and explore branched gameplay paths without restarting from scratch.

## Examples

**Good: Grind party XP on a route.**
The agent starts the server, confirms `/health` returns OK, reads `/party` to verify current levels and HP, then issues a grinder combo sequence looped 60 times. Afterward it reads `/party` again to confirm level-ups and saves the state.

**Good: Execute a wild-Pokémon catch loop.**
The agent sends `["A"]` repeatedly, reads `/battle` to detect encounter state, checks 0xD05E for battle start, deploys a weakening move, then sends a `POKEBALL` combo. On success it reads `/party` to verify the caught count at 0xD721 and saves.

**Good: Route navigation with checkpoint recovery.**
Before entering a cave (high wild-encounter area), the agent saves state with `POST /save`. If the party faints during navigation, the agent loads the checkpoint and tries an alternate path or uses a Repel item combo.

**Good: Shiny-hunting automation.**
The agent loops encounter sequences (`["A"]` repeated with short delays between encounters), reads the opposing Pokémon's species ID from RAM each frame, compares against the shiny PID, and only stops when a match is found — then calls out the result and saves.

## Anti-Patterns

**Anti-Pattern 1: Sending buttons without reading RAM first.**
Blindly pressing buttons without reading `/battle` or menu state leads to desync — the agent presses A expecting "fight" but the cursor is on "run". Always read state, then act.

**Anti-Pattern 2: Mixing batch-lesson meta-content into gameplay skill.**
The skill file currently contains lessons about the patch tool, YAML block scalars, and batch sizing strategies. These belong in an agent worklog, not in a reusable gameplay skill. Keep the skill focused on its domain.

**Anti-Pattern 3: Using the save endpoint as a database commit.**
`POST /save` captures the full emulator state (ROM position, RAM, timer, sprite coordinates). Calling it every frame or after every button press bloats disk and slows gameplay. Use it only at meaningful checkpoints (before a gym battle, after catching a rare Pokémon).

**Anti-Pattern 4: Hard-coding RAM addresses across games.**
The RAM map shown here is for Pokémon Red/Blue only. Pokémon Crystal uses different addresses for party data, item storage, and battle state. Always validate the target ROM before referencing specific addresses.

## When NOT to Use

- **Non-Pokémon Game Boy games.** The RAM map, battle-state parser, and combo sequences are Pokémon-specific. For other GB/C games, use a generic pyboy skill.
- **Real-time or action games (e.g., Super Mario).** The headless emulator has no frame-render and cannot react to on-screen events at sub-second speed. This skill is for turn-based RPGs only.
- **Competitive online battles.** Showdown-style simulations or link-cable multiplayer require real-time opponent decisions and latency-sensitive input — not supported.
- **Visual-feedback-dependent tasks.** If the strategy requires seeing the screen (e.g., maze navigation based on map tiles), pyboy's headless mode provides no pixel data.
- **Emulator development or debugging.** This skill consumes the emulator API; it is not designed to debug pyboy internals or patch the emulator itself.
- **ROM-patching or game-hacking projects.** Writing arbitrary RAM values or injecting assembly is outside the scope of this consumer-layer skill.

## Cross-References

- [pyboy documentation](https://github.com/Baekalfen/PyBoy) — underlying Game Boy emulator
- [Pokémon Red/Blue RAM Map](https://datacrystal.romhacking.net/wiki/Pok%C3%A9mon_Red/Blue:RAM_map) — comprehensive address reference
- [gbdev Pan Docs](https://gbdev.io/pandocs/) — original Game Boy hardware specification
- [Pokémon Crystal RAM Map](https://datacrystal.romhacking.net/wiki/Pok%C3%A9mon_Crystal:RAM_map) — if targeting Gen 2 ROMs
- Modal skill — for deploying the game server on serverless GPU infra for 24/7 uptime
