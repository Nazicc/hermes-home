---
name: pokemon-player
description: "Use when playing Pokemon games autonomously via headless emulation. Starts a game server, reads structured game state from RAM, makes strategic decisions, and sends button inputs — all from the terminal. Also supports mGBA/DeSmuME/BizHawk emulators for GBA/NDS titles. NOT for: non-Pokemon games, competitive online battles, real-time gaming, or when visual feedback is required."
category: gaming
---

# Pokémon Player — Emulator Automation and Game Scripting

Automate Pokémon gameplay across Game Boy (pyboy), GBA (mGBA), NDS (DeSmuME), and multi-system (BizHawk) emulators. Read game state from memory, make strategic decisions, and send button inputs programmatically.

## Architecture

- **pyboy** — pure Python Game Boy emulator; run headless (`--disable-render`)
- **Lua scripts** — embedded in save state; read/write RAM, push button combos
- **game-server.py** — Flask API wrapping pyboy + Lua bridge; exposes RAM addresses as REST endpoints
- **strategy/** — decision engine (type advantages, move priority, HP thresholds)
- **button_inputs/** — pre-built combo sequences (grinding, shiny hunting, etc.)

## When to Use

- Playing Pokémon games automatically (Gen 1-5)
- Training Pokémon for battle strategies
- Completing in-game tasks and quests
- Mass catching or farming Pokémon
- Building AI agents that play Pokémon games
- Scripting repetitive tasks (EV training, shiny hunting, egg hatching)
- Analyzing game mechanics and data structures

**Key features:**
- **Emulator control**: Launch, pause, resume, and quit emulators
- **Input automation**: Send button presses and sequences
- **Memory reading**: Read RAM values for game state (HP, level, position)
- **Lua scripting**: Write scripts that run inside the emulator
- **Bot frameworks**: Pre-built patterns for common Pokémon tasks

## Installation

### pyboy (Gen 1/2 — headless game server)

```bash
pip install pyboy
# Clone the repo with game-server.py and strategy engine
git clone https://github.com/your-org/pokemon-player ~/.hermes/pokemon-player
```

### mGBA / DeSmuME (GBA/NDS)

```bash
# macOS
brew install mgba desmume

# Linux
sudo apt install mgba-qt desmume
```

## Startup — pyboy Game Server

```bash
# 1. Start game server
cd ~/.hermes/pokemon-player
python game-server.py --rom PokemonRed.gb --port 5000 &

# 2. Verify server is up
curl http://localhost:5000/health  # should return {"status": "ok", "state": "playing"}

# 3. Check RAM is readable
curl http://localhost:5000/ram?addr=0xC000  # HP of first party Pokemon
```

## Launching Emulators (GBA/NDS)

```bash
# mGBA (GBA)
mgba /path/to/pokemon-emerald.gba

# DeSmuME (DS)
desmume /path/to/pokemon-platinum.nds
```

### Send input via socket (mGBA)

```bash
echo -n 'A' | nc -q0 localhost 8888
```

### Read game state with Lua (mGBA)

```lua
-- read-pokemon.lua
memory.usememorydomain("WRAM")
local species = memory.readbyte(0x02024284)
local hp = memory.readword(0x0202428A)
print(string.format("Species: %d, HP: %d/%d", species, hp, memory.readword(0x0202428C)))
```

## RAM Map (Pokémon Red/Blue)

| Address | Size | Description |
|---------|------|-------------|
| 0xC000–0xC04F | 80 | Party Pokemon (6 × 44 bytes each) |
| 0xD058 | 1 | Current HP (low byte) |
| 0xD059 | 1 | Current HP (high byte) |
| 0xD016 | 1 | Current menu/overworld state |
| 0xD05E | 1 | Battle state (0=none, 1=enemy appeared, 2=battle) |
| 0xCC4B | 1 | Badge flags |
| 0xD721 | 1 | Pokemon caught flag |

## Key Endpoints (pyboy Game Server)

- `GET /ram?addr=0xXXXX` — read raw RAM at hex address
- `GET /party` — parse all 6 Pokemon: species, level, HP, status
- `GET /battle` — current battle state, enemy Pokemon, available moves
- `POST /button` — send a button press: `{"button": "A"}`, `{"button": "START"}`, etc.
- `POST /combo` — send a sequence: `{"sequence": ["LEFT", "A", "DOWN", 0.1, ...]}`
- `POST /save?name=mysave.state` — persist emulator state
- `GET /health` — health check

## Usage

### pyboy Game Server

```bash
# Basic gameplay
curl -X POST http://localhost:5000/button -d '{"button":"A"}'

# Grind XP for 5 minutes
curl -X POST http://localhost:5000/combo -d '{"sequence":["A",0.5,"LEFT",0.3,"A",0.5,"B",0.1],"loop":120}'

# Check party status
curl http://localhost:5000/party | jq '.[] | {species, level, hp}'

# Save progress
curl -X POST http://localhost:5000/save -d '{"name":"route1"}'
```

## Emulator Comparison

| Emulator | Systems | Scripting | Memory Access | Speed |
|----------|---------|-----------|---------------|-------|
| mGBA | GBA, GBC, GB | Lua, socket | Full RAM read/write | Fast |
| DeSmuME | NDS | Lua, CLI | Limited | Moderate |
| BizHawk | GBA, NDS, NES, SNES, N64 | Lua | Full | Heavy |
| PyBoy | GB, GBC | Python | Full | Fast |

## Common Patterns

### Automated shiny hunting

```bash
# Lua script to reset until shiny encounter
mgba --lua=shiny_hunter.lua pokemon-emerald.gba
```

### Batch EV training

1. Launch emulator with speed-up
2. Send battle sequence repeatedly
3. Read stat changes to verify
4. Switch Pokémon when done

### Memory map reference

Common addresses vary by game. Use tools like PKHeX or BizHawk RAM Search to discover offsets for specific games.

## Purpose

To give an AI agent the ability to play Pokémon Game Boy titles (Red, Blue, Yellow, Crystal, etc.) entirely via headless emulation. The agent reads structured game state from emulator RAM, uses a decision engine for battle/movement strategy, and sends button input sequences through a REST API — no screen capture or human-in-the-loop required. This turns turn-based RPG gameplay into a programmable, scriptable automation task suitable for server environments.

## Why This Works

**Concept 1: RAM-as-API.** Rather than parsing pixels or OCR-ing a screen, the skill exposes emulator RAM addresses (party HP, battle state, menu position, badge flags) as structured JSON endpoints. The agent can make deterministic, low-latency decisions based on exact game state — no vision model, no screenshot latency.

**Concept 2: Combo Sequences as Macro Primitives.** Button presses are composed into parameterized sequences (e.g., `["A", 0.5, "LEFT", 0.3, "A"]`) that can be looped. This lets the agent execute multi-step grinding, catching, or movement routines as single atomic calls, reducing round-trips and API overhead.

**Concept 3: Save-State Checkpointing.** The emulator saves and loads full game state snapshots via `POST /save` / `POST /load`. This allows the agent to checkpoint before risky battles, retry failed encounters, and explore branched gameplay paths without restarting from scratch.

**Concept 4: In-Process Lua Scripting.** Lua scripts run inside the emulator's address space, giving them direct access to RAM, save states, and frame-level timing. This avoids IPC overhead and enables real-time decision making.

## Examples

**Good: Grind party XP on a route.**
The agent starts the server, confirms `/health` returns OK, reads `/party` to verify current levels and HP, then issues a grinder combo sequence looped 60 times. Afterward it reads `/party` again to confirm level-ups and saves the state.

**Good: Execute a wild-Pokémon catch loop.**
The agent sends `["A"]` repeatedly, reads `/battle` to detect encounter state, checks 0xD05E for battle start, deploys a weakening move, then sends a `POKEBALL` combo. On success it reads `/party` to verify the caught count at 0xD721 and saves.

**Good: Route navigation with checkpoint recovery.**
Before entering a cave (high wild-encounter area), the agent saves state with `POST /save`. If the party faints during navigation, the agent loads the checkpoint and tries an alternate path or uses a Repel item combo.

**Good: Shiny-hunting automation.**
The agent loops encounter sequences (`["A"]` repeated with short delays between encounters), reads the opposing Pokémon's species ID from RAM each frame, compares against the shiny PID, and only stops when a match is found — then calls out the result and saves.

**Good: Multi-instance farming.**
Launch three emulator instances simultaneously (one per generation), farm Poké Dollars by automating the Elite Four rematch on each, and aggregate the results into a single log file.

## Anti-Patterns

**Anti-Pattern 1: Sending buttons without reading RAM first.**
Blindly pressing buttons without reading `/battle` or menu state leads to desync — the agent presses A expecting "fight" but the cursor is on "run". Always read state, then act.

**Anti-Pattern 2: Hardcoding memory addresses without version checks.**
Pokémon game addresses differ across versions (e.g., Emerald vs. FireRed). A script written for one ROM silently reads garbage on another — always verify the ROM hash or detect version from a known signature address first.

**Anti-Pattern 3: Polling game state at maximum frame rate.**
Reading memory every frame (60 FPS) burns CPU and can desync emulator timing. Poll at 5-10 Hz for most tasks, or use emulator-provided callbacks — the game state changes only on specific events (turn start, menu open).

**Anti-Pattern 4: Sending inputs without synchronization delays.**
Emulator inputs are buffered — sending 20 directional inputs in rapid succession before the game processes frame 1 causes all inputs to be dropped or queued incorrectly. Always insert frame-count delays between input sequences.

**Anti-Pattern 5: Assuming all emulators share the same scripting API.**
mGBA uses `memory.readbyte()`, DeSmuME uses `memory.readbyte()` with different memory domains, BizHawk wraps everything under `mainmemory.readbyte()`. Write emulator-specific adapters rather than trying to abstract them all behind one interface.

**Anti-Pattern 6: Using the save endpoint as a database commit.**
`POST /save` captures the full emulator state (ROM position, RAM, timer, sprite coordinates). Calling it every frame or after every button press bloats disk and slows gameplay. Use it only at meaningful checkpoints (before a gym battle, after catching a rare Pokémon).

## When NOT to Use

- **Non-Pokémon Game Boy games.** The RAM map, battle-state parser, and combo sequences are Pokémon-specific.
- **Real-time or action games (e.g., Super Mario).** The headless emulator has no frame-render and cannot react to on-screen events at sub-second speed. This skill is for turn-based RPGs only.
- **Competitive online battles.** Showdown-style simulations or link-cable multiplayer require real-time opponent decisions and latency-sensitive input — not supported.
- **Visual-feedback-dependent tasks.** If the strategy requires seeing the screen (e.g., maze navigation based on map tiles), pyboy's headless mode provides no pixel data.
- **Emulator development or debugging.** This skill consumes the emulator API; it is not designed to debug pyboy internals or patch the emulator itself.
- **ROM-patching or game-hacking projects.** Writing arbitrary RAM values or injecting assembly is outside the scope of this consumer-layer skill.
- **You only need Game Boy / Game Boy Color.** Use **PyBoy** which has native Python bindings and simpler setup.

## Cross-References

- [pyboy documentation](https://github.com/Baekalfen/PyBoy) — underlying Game Boy emulator
- [Pokémon Red/Blue RAM Map](https://datacrystal.romhacking.net/wiki/Pok%C3%A9mon_Red/Blue:RAM_map) — comprehensive address reference
- [gbdev Pan Docs](https://gbdev.io/pandocs/) — original Game Boy hardware specification
- [Pokémon Crystal RAM Map](https://datacrystal.romhacking.net/wiki/Pok%C3%A9mon_Crystal:RAM_map) — if targeting Gen 2 ROMs
- **pyboy** — Python-native Game Boy emulator with scripting support, ideal for Gen 1/2 games
- **bizhawk** — Multi-system emulator with Lua scripting for GBA, NDS, NES, SNES, and N64 Pokémon titles
- Modal skill — for deploying the game server on serverless GPU infra for 24/7 uptime
