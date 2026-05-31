---
name: rust-monorepo-deep-dive
description: "Systematically analyze a Rust monorepo via GitHub raw content — for understanding architecture, daemon IPC patterns, CDP/protocol implementations, and skill systems. Use when given a GitHub URL or local path to a Rust project and asked to deeply understand its architecture, design patterns, IPC mechanisms, or system structure. NOT for: writing or debugging Rust code, debugging compilation errors, non-Rust repositories, or quick lookup of a single function."
category: general
---

## When to Use

Triggered when user provides a GitHub URL or local path to a Rust project and asks to deeply understand its architecture, design patterns, IPC mechanisms, or system structure. NOT for writing or debugging Rust code, debugging compilation errors, or quick lookup of a single function.

## Sequential File Discovery Order

Read files **in this exact order** — each reveals what to look for next:

1. **README.md** → project scope, key features, architecture overview
2. **`Cargo.toml`** (root) → workspace members, key dependencies (indicates IPC pattern: tokio-unix-sockets, CDP, embedded-skills)
3. **`src/main.rs`** (root or binary crate) → entry point, CLI argument structure, daemon vs one-shot behavior
4. **`src/bin/` or binary crate `main.rs`** → how the daemon is spawned, socket path, startup logic
5. **`src/daemon.rs`** or equivalent → IPC server loop, connection handling, Arc+RwLock state management
6. **`src/connection.rs`** or equivalent → protocol framing, JSON message parsing, Unix socket transport
7. **`src/skills.rs`** or equivalent → skill loading, how external tools/commands are dispatched
8. **Any `src/stream/` module** → streaming response patterns, broadcast-channel or mpsc for multi-client

## IPC Architecture Patterns

**Common Rust daemon IPC patterns:**

| Pattern | Indicators | Questions to Answer |
|---------|-----------|---------------------|
| Unix Domain Socket + JSON | `tokio-unix-sockets`, `UnixStream`, `/tmp/*.sock`, `SocketAddr::Unix` | How does CLI communicate with daemon? JSON-RPC? Line-delimited JSON? |
| Arc + RwLock state | `Arc<RwLock<>>` in source | How is state shared across connections? |
| Broadcast channel for fan-out | `broadcast::channel`, multiple consumers | Multiple clients or tabs? |
| Streaming/SSE | `Event`, `Stream`, `async_stream`, `tokio_stream` | How does the daemon push data to clients? |
| Multi-process | `tokio::process::Command`, `child`, `spawn` | Does it spawn child processes? Which? |
| WASM/JS runtime | `wasm`, `quickjs`, `deno_core`, `v8` | Is JavaScript evaluation built-in? |
| Embedded skills | `rust-embed`, `include_bytes!` in Cargo.toml | Are skills bundled into the binary? |
| Config-driven behavior | `config.yaml`, `Config`, `settings` | Where does configuration live? |

### CDP vs Playwright

- **Pure CDP**: Custom implementation of Chrome DevTools Protocol over Unix socket. More control, less dependencies. Look for `cdp` in dependencies or `devtools` in `Cargo.toml`.
- **Playwright/RWebDriver**: Offloads browser automation. Look for `playwright` or `webdriver` in `Cargo.toml`.
- **CDP-based browser indicators**: `cdp`, `chrome-devtools`, `browser`, `page`, `frame` in filenames or imports.

## Evaluation Dimensions

Assess the project along these dimensions:

**1. IPC Mechanism**
- How does the CLI communicate with the daemon? (UDS + JSON, HTTP, stdio, gRPC?)
- Is the protocol simple enough to reimplement in Python/Hermes?
- Could Hermes Agent connect as a client?

**2. Streaming Architecture**
- Does the daemon support server-sent events or streaming responses?
- How does it handle concurrent connections?
- Is there a max concurrent session limit?

**3. Skill/Extension System**
- How are skills defined and loaded?
- Is there a manifest, schema, or registry?
- Can skills be added at runtime?

**4. Browser Automation Approach**
- CDP direct vs WebSocket proxy vs puppeteer/playwright-based?
- How does it handle multi-tab, context, or session isolation?
- What browser state does it track (cookies, storage, cache)?

## Depth Guidance

Stop when architecture is clear. Typically 4-6 files suffices:
- README (scope)
- Cargo.toml (structure + deps)
- main.rs (entry)
- 1-2 core modules (daemon, connection, or skills)

Avoid over-collecting. If a file doesn't reveal new architectural information, skip it.

## Common Mistakes to Avoid

- **Don't read every file** — Rust projects have many generated/boilerplate files. Focus on `src/` top-level and key modules.
- **Don't miss the workspace structure** — many Rust projects have `crates/{name}/Cargo.toml` that reveal the architecture.
- **Don't assume HTTP** — Rust CLI tools often use Unix Domain Sockets for speed. Check for `tokio::net::UnixStream` or `.sock` patterns.
- **Don't overlook the streaming layer** — many daemons use `async_stream!` or `StreamExt` for real-time output.

## GitHub Raw Content URL Pattern

Fetch raw content via:

https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}


For directory listing, use GitHub API:

https://api.github.com/repos/{owner}/{repo}/contents/{path}


## Output Format

Structure the analysis as:
1. **Project Overview** — purpose and scope
2. **Architecture** — modular structure, workspace layout
3. **IPC Pattern** — how CLI and daemon communicate
4. **Key Implementation Details** — notable patterns (CDP, skill system, etc.)
5. **Dependencies** — notable crates and their roles
6. **Insights for Hermes** — what lessons can be drawn for Hermes Agent architecture
