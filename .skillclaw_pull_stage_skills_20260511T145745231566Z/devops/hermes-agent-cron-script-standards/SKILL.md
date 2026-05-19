---
name: hermes-agent-cron-script-standards
description: "Use when writing, editing, or debugging cron prerun/checker scripts for hermes-agent, specifically when creating, updating, or fixing anything in `cron/` or `~/.hermes/scripts/`. Includes any work on `rss_health_checker.py`, `make deploy`, or investigating cron job failures. NOT for: general agent logic, non-cron tooling, or scripts outside the cron/pre-run context."
category: devops
---

# Cron Prerun/Checker Script Standards

## Critical Rule: Stdlib Only (No External Dependencies)

**The hermes-agent venv runs Python 3.14.4 and does NOT ship with third-party packages like httpx, requests, feedparser, or any pip-installed module.**

The cron scheduler runs scripts via `sys.executable` (the venv python), not anaconda python or system python. Any third-party import will fail silently or with `ModuleNotFoundError` at cron runtime.

**Always use stdlib only:**
- HTTP: `urllib.request` + `urllib.error` — replaces httpx/requests
- XML/RSS: `xml.etree.ElementTree` — replaces feedparser
- Concurrency: `concurrent.futures.ThreadPoolExecutor`
- JSON, subprocess, pathlib, socket, datetime, csv, re, logging — all stdlib, use freely

**Empirical evidence (2026-04-26):** `rss_health_checker.py` originally used httpx. During health checks, Dark Reading, The Register, and 4hou timed out consistently. After switching to `urllib.request`, all 6/6 sources became healthy. urllib.request also avoids httpx's certificate/connection quirks on this system.

## Key Principles

1. **stdlib only** — do NOT import httpx, requests, aiohttp, or any third-party HTTP library. Use `urllib.request` instead.
2. **zero-dependency** — no `pip install`, no venv activation, no external packages
3. **JSON output** — scripts must emit structured JSON to stdout for upstream consumption
4. **concurrency** — use `concurrent.futures.ThreadPoolExecutor` for parallel checks
5. **absolute shebang** — use `#!/usr/bin/env python3`, not a hardcoded Python path

## Deployment Paths

- **Source of truth:** `cron/<script>.py` in the hermes-agent repo
- **Runtime path:** `~/.hermes/scripts/<script>.py`
- **Deployment:** `make deploy` syncs `cron/` → `~/.hermes/scripts/`
- **Post-commit hook:** `scripts/git-hooks/post-commit` auto-deploys on push

Verify post-commit hook is installed:
bash
ls -la .git/hooks/post-commit


## Script Requirements

1. **Shebang:** `#!/usr/bin/env python3` (not a hardcoded path — venv python varies)
2. **Stdlib imports only:** no pip packages
3. **Absolute paths or sys.executable-aware:** scripts that call other scripts should use `sys.executable -m <module>` or resolve paths relative to the repo root
4. **Three output modes:**
   - **Silent/pass mode** (cron invocation): exit 0 for healthy, exit 1 for degraded/critical. Output only on failure or `--verbose`
   - **Human-readable mode** (`--verbose` or no args): structured status output
   - **JSON mode** (`--json`): machine-parseable output for upstream consumers

## Environment

- Python: `sys.executable` (venv python, no pip packages)
- HERMES_HOME: `~/.hermes/`
- WORKDIR: hermes-agent repo root
- Use `pathlib.Path.home() / ".hermes"` for user-level paths; `pathlib.Path(__file__).parent` for script-local paths

## stdlib HTTP Pattern

python
import urllib.request
import urllib.error
import socket

# Set default timeout for all socket operations
socket.setdefaulttimeout(15.0)

def fetch_url(url: str, timeout: float = 15.0) -> tuple[int, bytes]:
    """Returns (http_code, body_bytes). Raises on network error."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; HermesBot/1.0)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()

# Exception handling:
# - urllib.error.HTTPError:   http_code >= 400 (includes 403 WAF, 404, 500...)
# - urllib.error.URLError:    DNS/connection failure (check .reason for details)
# - socket.timeout:            timeout exceeded
# - OSError:                   connection refused, network unreachable


### HTTP Status Classification

python
def classify_status(http_code: int) -> str:
    if http_code == 200:
        return "healthy"
    elif http_code == 403:
        return "waf_blocked"   # Cloudflare / WAF returned 403
    elif 400 <= http_code < 500:
        return "http_error"    # client error
    elif http_code >= 500:
        return "degraded"     # server-side issue
    else:
        return "http_error"


### Timeout Hierarchy

python
CONNECT_TIMEOUT = 10.0   # DNS/TCP connect
READ_TIMEOUT    = 15.0   # data transfer
socket.setdefaulttimeout(READ_TIMEOUT)   # applies to all socket operations


## Quick Reference: Python Stdlib Modules

| Need | Use |
|------|-----|
| HTTP requests | `urllib.request`, `urllib.error` |
| JSON | `json` |
| XML/RSS parsing | `xml.etree.ElementTree` |
| Concurrency | `concurrent.futures` |
| Subprocess | `subprocess` |
| Timeouts | `socket.setdefaulttimeout` |
| Dates | `datetime`, `calendar` |
| CSV | `csv` |
| Path manipulation | `pathlib` |
| Regex | `re` |
| Logging | `logging` |

## Common Failure Modes

1. **httpx/requests import fails** — use `urllib.request` instead
2. **feedparser import fails** — use `xml.etree.ElementTree` for RSS parsing
3. **Script runs interactively but fails in cron** — check `sys.executable` matches; third-party packages in anaconda python are not available to the cron scheduler
4. **Silent failure** — always test with `python3 ~/.hermes/scripts/<script>.py --json` before assuming health

## Testing

Run locally:
bash
cd /Users/can/.hermes/hermes-agent
python3 ~/.hermes/scripts/<script>.py --json


Validate JSON output:
bash
python3 ~/.hermes/scripts/<script>.py --json | python3 -m json.tool > /dev/null && echo "valid JSON"


Verify syntax:
bash
python3 -m py_compile ~/.hermes/scripts/<script>.py


Check for non-stdlib imports:
bash
grep -E "^import (httpx|requests|feedparser)" ~/.hermes/scripts/<script>.py  # should return nothing


Check concurrency:
bash
# Run twice in parallel and verify no race conditions
python3 ~/.hermes/scripts/<script>.py &
python3 ~/.hermes/scripts/<script>.py &
wait


## RSS Health Checker Specifics

**File locations:**
- Repo:   `cron/rss_health_checker.py`
- Runtime: `~/.hermes/scripts/rss_health_checker.py`

**6 monitored RSS sources:**
| Name | URL | Tag |
|------|-----|-----|
| FreeBuf | https://www.freebuf.com/feed | 技术社区 |
| 4hou | https://www.4hou.com/feed | 技术社区 |
| 安全派 | https://secbug.org/feed | 技术社区 |
| Paper Seebug | https://paper.seebug.org/rss/ | 技术社区 |
| Dark Reading | https://www.darkreading.com/rss/all.xml | 国际资讯 |
| The Register | https://www.theregister.com/security/headlines.atom | 国际资讯 |

**Status values:** `healthy` | `degraded` | `http_error` | `timeout` | `unreachable` | `parse_error` | `waf_blocked`

**Output:** JSON array of source objects with `name`, `url`, `status`, `http_code`, `size_bytes`, `response_time_ms`, `error`, `entries_count`.

**Debugging a failing source:**
bash
python3 -c "
import urllib.request, urllib.error, socket
socket.setdefaulttimeout(15.0)
url = 'https://www.4hou.com/feed'
try:
    r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=15.0)
    print(r.status, len(r.read()))
except urllib.error.HTTPError as e:
    print('HTTP', e.code, e.reason)
except Exception as ex:
    print(type(ex).__name__, ex)
"


## Validation Checklist

Before committing a cron script change:
- [ ] Runs successfully with `python3 ~/.hermes/scripts/<script>.py --json` (venv python, not anaconda)
- [ ] No third-party imports (httpx, requests, feedparser, etc.)
- [ ] Synced to `~/.hermes/scripts/` via `make deploy`
- [ ] Valid JSON output
- [ ] Working tree clean (`git status --short`)

