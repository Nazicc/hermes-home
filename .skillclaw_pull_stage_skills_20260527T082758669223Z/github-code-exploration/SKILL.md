---
name: github-code-exploration
description: "Explore public GitHub repository source code structure, retrieve file contents, and analyze architecture patterns. Use when: analyzing unfamiliar repositories, comparing implementations, auditing code structure, understanding a project's architecture from source, or needing environment-specific API/CLI/SDK patterns. Supports GitHub Contents API and raw.githubusercontent.com for reading files. NOT for: authenticated API calls, GitHub Actions workflow analysis, or non-GitHub code exploration."
category: general
---

# GitHub Code Exploration

## Use When
- Analyzing unfamiliar open-source project architecture
- Finding environment-specific API patterns, CLI tool structures, or SDK usage
- Reading source files to understand internal mechanisms
- Comparing implementations across repositories
- Auditing code structure or dependencies

## Prerequisites
- Know the GitHub owner and repository name
- Optionally know the branch (defaults to `main`, fallback to `master`)

## Step 1: Check Rate Limit (Optional)

bash
curl -s "https://api.github.com/rate_limit" 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
core = d.get('rate', {})
print(f'Remaining: {core.get(\"remaining\", 0)} / {core.get(\"limit\", 0)}')
print(f'Reset: {core.get(\"reset\", 0)}')
"


The unauthenticated API allows 60 requests/hour. If limited, use Contents API as primary method.

## Step 2: Get Repository Overview

bash
curl -s "https://api.github.com/repos/<owner>/<repo>" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Description:', d.get('description',''))
print('Stars:', d.get('stargazers_count',''))
print('Default branch:', d.get('default_branch',''))
print('Language:', d.get('language',''))
"


## Step 3: Explore Source Tree

### Recommended: Tree API (one request for entire structure)

bash
curl -s "https://api.github.com/repos/<owner>/<repo>/git/trees/HEAD?recursive=1" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for item in sorted(d.get('tree', []), key=lambda x: x['path']):
    print(item['type'], item['path'])
" | head -200


- `type` values: `blob` (file), `tree` (directory)
- Filter for specific file types:
  - `| grep "^blob" | grep "\.rs$"` → Rust files
  - `| grep "^blob" | grep "\.py$"` → Python files
  - `| grep "^tree" | grep "^tree src/"` → subdirectories under src/

### Fallback: Contents API (recursive directory listing)

bash
curl -s "https://api.github.com/repos/<owner>/<repo>/contents/<path>" | python3 -c "
import sys, json
d=json.load(sys.stdin)
if isinstance(d, list):
    for item in sorted(d, key=lambda x: x['name']):
        print(item['type'], item['name'])
else:
    print(d.get('type'), d.get('name'))
"


Start with empty path (root), then drill into subdirectories like `src/`, `src/khoj/`, etc.

## Step 4: Read Source Files

### Prefer: raw.githubusercontent.com

bash
curl -s https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>


- Returns raw file content (code, markdown, config)
- For large files (>1MB), add `-L` to follow redirects

### Fallback: Contents API with base64 decoding

bash
curl -s "https://api.github.com/repos/<owner>/<repo>/contents/<path>" | python3 -c "
import sys, json, base64
d = json.load(sys.stdin)
content = d.get('content', '')
print(base64.b64decode(content).decode('utf-8'))
"


### Alternative: Use download_url

bash
curl -s $(curl -s "https://api.github.com/repos/<owner>/<repo>/contents/<path>" | python3 -c "import sys,json; print(json.load(sys.stdin)['download_url'])")


## Key Files to Read First

| File Type | Why It Matters |
|---|---|
| `package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod` | Dependencies, project type |
| `Makefile`, `Dockerfile`, `docker-compose.yml` | Build/run procedures |
| `README.md`, `ARCHITECTURE.md` | High-level overview |
| `src/main.*`, `cmd/*/main.go`, `cli/src/main.rs` | Entry points |
| `src/*/router.*`, `src/*/handler.*` | API/CLI routing |
| `src/*/config.*`, `settings.*` | Environment variables, ports, paths |
| `src/*/adapter.*`, `src/*/service.*` | Business logic layer |
| `src/*/model.*`, `src/*/entity.*` | Data models, DB schemas |
| `tests/`, `*_test.*`, `test_*.py` | Test patterns, edge cases |

**By language:**
- **Python**: `setup.py`, `pyproject.toml`, `src/<package>/__init__.py`, `src/<package>/main.py`, `src/<package>/routers/`
- **Rust**: `Cargo.toml`, `src/main.rs`, `src/lib.rs`, `cli/src/`, `daemon/`
- **JS/TS**: `package.json`, `src/index.ts`, `src/cli.ts`
- **Go**: `go.mod`, `cmd/`, `internal/`

## Language-Specific Analysis

### Python Projects (FastAPI/Flask/Django)

bash
curl -s "https://api.github.com/repos/<owner>/<repo>/contents/src" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for x in sorted(d, key=lambda i: i['name']): print(x['type'], x['name'])
"


Focus on: `__init__.py` (exports), `models.py` (ORM), `adapters.py` (DB queries), `views.py`/`routers.py` (API endpoints). For Django ORM projects, the models directory reveals data architecture.

### Rust Projects

bash
curl -s "https://api.github.com/repos/<owner>/<repo>/contents/<src_dir>/src" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for x in sorted(d, key=lambda i: i['name']): print(x['type'], x['name'])
"


Focus on: `main.rs` (entry), `Cargo.toml` (deps), `cli/src/` (CLI layer), `daemon/` (background service).

### Monorepos

bash
curl -s "https://api.github.com/repos/<owner>/<repo>/contents/" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for x in sorted(d, key=lambda i: i['name']): print(x['type'], x['name'])
"


Identify package directories, shared libraries, workspace configs. Check for `Makefile`, `justfile`, or root-level task runner.

## Filter for Relevant Code

Search for patterns in specific files:

bash
curl -s https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path> | grep -n "def \|class \|async def \|fn "


Get line numbers for targeted reading:

bash
curl -s https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path> | cat -n


Read specific line ranges:

bash
curl -s https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path> | sed -n '100,200p'


## Troubleshooting

| Problem | Solution |
|---|---|
| API rate limited | Wait for reset, or switch to Contents API |
| raw.githubusercontent.com empty/403 | Use Contents API with base64 decoding or download_url |
| Tree returns truncated results | Use Contents API and recurse manually into subdirectories |
| Large file (>1MB) fails on raw | Use Contents API with base64 decoding, or download_url |
| File encoding issues | Add `-H "Accept: application/vnd.github.v3.raw"` |

## Key Patterns

- **Always start with top-level listing** to understand project type (monorepo? single-package?)
- **Prioritize `src/`, `lib/`, `app/` directories** over root-level config files
- **Check for `__init__.py`, `mod.rs`, or `index.ts`** — these often contain the main public API
- **Use tree API when available** — one request gets the entire structure
- **When raw returns empty** — immediately switch to Contents API with base64 decoding
- **For large monorepos** — check for task runner files to understand build/test structure
- **Search for `class \|def \|async def \|fn `** to find key patterns in source files
