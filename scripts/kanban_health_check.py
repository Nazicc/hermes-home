#!/usr/bin/env python3
"""Kanban health check — inspect board state and report anomalies.

Checks:
  1. DB accessibility and WAL integrity
  2. Dispatcher liveness (gateway process or standalone daemon)
  3. Stuck tasks: running tasks with expired claims
  4. Stale claims: running tasks whose worker PID is dead
  5. Heartbeat staleness: running tasks with no recent heartbeat
  6. Blocked tasks with circuit-breaker trips (consecutive_failures > 0)
  7. Unassigned ready tasks (no assignee = dispatcher will skip)
  8. Orphaned workspaces (workspace dirs with no matching task)

Output: JSON report to stdout. Exit code 0 if healthy, 1 if any
CRITICAL issues, 2 if only WARNING issues.

Usage:
    python3 kanban_health_check.py [--board <slug>] [--json] [--quiet]
"""

from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLAIM_TTL_SECONDS = 15 * 60       # DEFAULT_CLAIM_TTL_SECONDS from kanban_db
HEARTBEAT_STALE_SECONDS = 10 * 60  # 10 min without heartbeat = stale
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_WARNING = "WARNING"
SEVERITY_OK = "OK"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hermes_home() -> Path:
    """Resolve the shared Hermes root (same logic as kanban_db.kanban_home)."""
    override = os.environ.get("HERMES_KANBAN_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    # Walk up from profile dir to root
    home = os.environ.get("HERMES_HOME", "")
    if home:
        p = Path(home).expanduser()
        if p.name == "profiles" and p.parent.exists():
            return p.parent
        return p
    return Path.home() / ".hermes"


def _db_path(board: Optional[str] = None) -> Path:
    """Resolve kanban.db path for a given board."""
    hermes_home = _hermes_home()
    env_db = os.environ.get("HERMES_KANBAN_DB", "").strip()
    if env_db:
        return Path(env_db).expanduser()

    if board and board != "default":
        return hermes_home / "kanban" / "boards" / board / "kanban.db"
    return hermes_home / "kanban.db"


def _pid_alive(pid: int) -> bool:
    """Check if a PID is alive (POSIX)."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _find_gateway_pid() -> Optional[int]:
    """Find the gateway process PID (hermes gateway or python run.py)."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "hermes.*gateway|run\\.py.*gateway"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Return the first match
            return int(result.stdout.strip().split("\n")[0])
    except Exception:
        pass
    return None


def _find_daemon_pid() -> Optional[int]:
    """Find a standalone kanban daemon process."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "hermes.*kanban.*daemon"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split("\n")[0])
    except Exception:
        pass
    return None


def _format_duration(seconds: int) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m}m"


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def check_db(db_path: Path) -> dict[str, Any]:
    """Check DB file exists, is readable, and WAL mode is active."""
    result: dict[str, Any] = {
        "check": "db_accessible",
        "path": str(db_path),
    }
    if not db_path.exists():
        result["severity"] = SEVERITY_CRITICAL
        result["message"] = f"kanban.db not found at {db_path}"
        return result

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row

        # Quick integrity check
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if integrity and integrity[0] != "ok":
            result["severity"] = SEVERITY_CRITICAL
            result["message"] = f"DB integrity check failed: {integrity[0]}"
            conn.close()
            return result

        # Count tasks by status
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"
        ).fetchall()
        status_counts = {r["status"]: r["cnt"] for r in rows}

        # Board count
        total = sum(status_counts.values())

        # DB file size
        db_size = db_path.stat().st_size

        result["severity"] = SEVERITY_OK
        result["message"] = f"DB OK — {total} tasks"
        result["details"] = {
            "total_tasks": total,
            "status_counts": status_counts,
            "db_size_bytes": db_size,
        }
        conn.close()
    except Exception as exc:
        result["severity"] = SEVERITY_CRITICAL
        result["message"] = f"Cannot open DB: {exc}"

    return result


def check_dispatcher() -> dict[str, Any]:
    """Check if the kanban dispatcher is running."""
    result: dict[str, Any] = {"check": "dispatcher_liveness"}

    gw_pid = _find_gateway_pid()
    daemon_pid = _find_daemon_pid()

    if gw_pid:
        result["severity"] = SEVERITY_OK
        result["message"] = f"Gateway dispatcher running (PID {gw_pid})"
        result["details"] = {"type": "gateway", "pid": gw_pid}
    elif daemon_pid:
        result["severity"] = SEVERITY_OK
        result["message"] = f"Standalone daemon running (PID {daemon_pid})"
        result["details"] = {"type": "daemon", "pid": daemon_pid}
    else:
        result["severity"] = SEVERITY_WARNING
        result["message"] = (
            "No dispatcher process found — tasks will not be dispatched. "
            "Start the gateway or run `hermes kanban daemon`."
        )
        result["details"] = {"type": None, "pid": None}

    return result


def check_stuck_tasks(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Find running tasks with expired claims (stuck = dispatcher should reclaim)."""
    now = int(time.time())
    results: list[dict[str, Any]] = []

    rows = conn.execute(
        "SELECT id, title, claim_lock, claim_expires, worker_pid, "
        "       last_heartbeat_at, started_at "
        "FROM tasks WHERE status = 'running' AND claim_expires IS NOT NULL "
        "  AND claim_expires < ?",
        (now,),
    ).fetchall()

    for row in rows:
        expired_ago = now - row["claim_expires"]
        pid = row["worker_pid"]
        pid_alive = _pid_alive(pid) if pid else False
        severity = SEVERITY_WARNING if pid_alive else SEVERITY_CRITICAL

        results.append({
            "check": "stuck_task",
            "severity": severity,
            "message": (
                f"Task {row['id']} claim expired {_format_duration(expired_ago)} ago"
                + (" (PID alive — will be extended)" if pid_alive
                   else " (PID dead — needs reclaim)")
            ),
            "details": {
                "task_id": row["id"],
                "title": row["title"],
                "claim_lock": row["claim_lock"],
                "claim_expires": row["claim_expires"],
                "expired_ago_seconds": expired_ago,
                "worker_pid": pid,
                "pid_alive": pid_alive,
                "last_heartbeat_at": row["last_heartbeat_at"],
            },
        })

    return results


def check_dead_workers(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Find running tasks whose worker PID is no longer alive."""
    results: list[dict[str, Any]] = []

    rows = conn.execute(
        "SELECT id, title, worker_pid, claim_lock, started_at "
        "FROM tasks WHERE status = 'running' AND worker_pid IS NOT NULL"
    ).fetchall()

    for row in rows:
        pid = row["worker_pid"]
        if pid and not _pid_alive(pid):
            results.append({
                "check": "dead_worker",
                "severity": SEVERITY_CRITICAL,
                "message": (
                    f"Task {row['id']} worker PID {pid} is dead "
                    f"(task stuck in 'running')"
                ),
                "details": {
                    "task_id": row["id"],
                    "title": row["title"],
                    "worker_pid": pid,
                    "claim_lock": row["claim_lock"],
                    "started_at": row["started_at"],
                },
            })

    return results


def check_heartbeat_staleness(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Find running tasks with stale heartbeats."""
    now = int(time.time())
    threshold = now - HEARTBEAT_STALE_SECONDS
    results: list[dict[str, Any]] = []

    rows = conn.execute(
        "SELECT id, title, worker_pid, last_heartbeat_at, claim_expires "
        "FROM tasks WHERE status = 'running' AND worker_pid IS NOT NULL "
        "  AND (last_heartbeat_at IS NULL OR last_heartbeat_at < ?)",
        (threshold,),
    ).fetchall()

    for row in rows:
        hb = row["last_heartbeat_at"]
        if hb is None:
            stale_for = "never"
        else:
            stale_for = _format_duration(now - hb)

        pid = row["worker_pid"]
        pid_alive = _pid_alive(pid) if pid else False

        results.append({
            "check": "stale_heartbeat",
            "severity": SEVERITY_WARNING if pid_alive else SEVERITY_CRITICAL,
            "message": (
                f"Task {row['id']} heartbeat stale ({stale_for})"
                + (" — PID alive" if pid_alive else " — PID dead")
            ),
            "details": {
                "task_id": row["id"],
                "title": row["title"],
                "worker_pid": pid,
                "last_heartbeat_at": hb,
                "pid_alive": pid_alive,
            },
        })

    return results


def check_blocked_tasks(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Find blocked tasks and tasks with consecutive failures."""
    results: list[dict[str, Any]] = []

    # Blocked tasks
    rows = conn.execute(
        "SELECT id, title, consecutive_failures, last_failure_error, max_retries "
        "FROM tasks WHERE status = 'blocked'"
    ).fetchall()

    for row in rows:
        results.append({
            "check": "blocked_task",
            "severity": SEVERITY_WARNING,
            "message": (
                f"Task {row['id']} is blocked"
                + (f" (consecutive_failures={row['consecutive_failures']})"
                   if row["consecutive_failures"] > 0 else "")
            ),
            "details": {
                "task_id": row["id"],
                "title": row["title"],
                "consecutive_failures": row["consecutive_failures"],
                "last_failure_error": row["last_failure_error"],
                "max_retries": row["max_retries"],
            },
        })

    # Running/todo tasks with non-zero failures (pre-blocked state)
    rows = conn.execute(
        "SELECT id, title, status, consecutive_failures, last_failure_error "
        "FROM tasks WHERE status IN ('ready', 'running') "
        "  AND consecutive_failures > 0"
    ).fetchall()

    for row in rows:
        results.append({
            "check": "failure_count",
            "severity": SEVERITY_WARNING,
            "message": (
                f"Task {row['id']} has {row['consecutive_failures']} "
                f"consecutive failure(s) (status={row['status']})"
            ),
            "details": {
                "task_id": row["id"],
                "title": row["title"],
                "status": row["status"],
                "consecutive_failures": row["consecutive_failures"],
                "last_failure_error": row["last_failure_error"],
            },
        })

    return results


def check_unassigned_ready(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Find ready tasks with no assignee (dispatcher will skip these)."""
    results: list[dict[str, Any]] = []

    rows = conn.execute(
        "SELECT id, title FROM tasks WHERE status = 'ready' AND assignee IS NULL"
    ).fetchall()

    for row in rows:
        results.append({
            "check": "unassigned_ready",
            "severity": SEVERITY_WARNING,
            "message": f"Task {row['id']} is ready but has no assignee (dispatcher will skip)",
            "details": {
                "task_id": row["id"],
                "title": row["title"],
            },
        })

    return results


def check_orphaned_workspaces(conn: sqlite3.Connection, board: Optional[str] = None) -> list[dict[str, Any]]:
    """Find workspace directories with no matching task."""
    results: list[dict[str, Any]] = []
    hermes_home = _hermes_home()

    if board and board != "default":
        ws_root = hermes_home / "kanban" / "boards" / board / "workspaces"
    else:
        ws_root = hermes_home / "kanban" / "workspaces"

    if not ws_root.is_dir():
        return results

    # Get all task IDs from DB
    task_ids = {
        r["id"] for r in conn.execute("SELECT id FROM tasks").fetchall()
    }

    for entry in ws_root.iterdir():
        if entry.is_dir() and entry.name not in task_ids:
            # Workspace dir exists but no matching task
            results.append({
                "check": "orphaned_workspace",
                "severity": SEVERITY_WARNING,
                "message": f"Workspace {entry.name} has no matching task",
                "details": {
                    "workspace_dir": str(entry),
                    "task_id": entry.name,
                },
            })

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_health_check(board: Optional[str] = None) -> dict[str, Any]:
    """Run all health checks and return a structured report."""
    now = int(time.time())
    db_path = _db_path(board)
    all_findings: list[dict[str, Any]] = []

    # 1. DB accessibility
    db_result = check_db(db_path)
    all_findings.append(db_result)

    db_ok = db_result.get("severity") == SEVERITY_OK
    if not db_ok:
        # Can't proceed with DB-dependent checks
        return {
            "timestamp": now,
            "board": board or "default",
            "db_path": str(db_path),
            "overall": SEVERITY_CRITICAL,
            "findings": all_findings,
            "summary": {
                "critical": 1,
                "warning": 0,
                "ok": 0,
            },
        }

    # Open DB for remaining checks (read-only)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    try:
        # 2. Dispatcher liveness
        all_findings.append(check_dispatcher())

        # 3. Stuck tasks (expired claims)
        all_findings.extend(check_stuck_tasks(conn))

        # 4. Dead workers
        all_findings.extend(check_dead_workers(conn))

        # 5. Heartbeat staleness
        all_findings.extend(check_heartbeat_staleness(conn))

        # 6. Blocked tasks / failure counts
        all_findings.extend(check_blocked_tasks(conn))

        # 7. Unassigned ready tasks
        all_findings.extend(check_unassigned_ready(conn))

        # 8. Orphaned workspaces
        all_findings.extend(check_orphaned_workspaces(conn, board))
    finally:
        conn.close()

    # Compute overall severity
    critical_count = sum(1 for f in all_findings if f.get("severity") == SEVERITY_CRITICAL)
    warning_count = sum(1 for f in all_findings if f.get("severity") == SEVERITY_WARNING)
    ok_count = sum(1 for f in all_findings if f.get("severity") == SEVERITY_OK)

    if critical_count > 0:
        overall = SEVERITY_CRITICAL
    elif warning_count > 0:
        overall = SEVERITY_WARNING
    else:
        overall = SEVERITY_OK

    # Extract DB details for top-level summary
    db_details = db_result.get("details", {})

    return {
        "timestamp": now,
        "board": board or "default",
        "db_path": str(db_path),
        "overall": overall,
        "findings": all_findings,
        "summary": {
            "critical": critical_count,
            "warning": warning_count,
            "ok": ok_count,
            "total_tasks": db_details.get("total_tasks", 0),
            "status_counts": db_details.get("status_counts", {}),
        },
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Kanban board health check")
    parser.add_argument("--board", default=None, help="Board slug (default: 'default')")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--quiet", action="store_true", help="Only show issues (no OK items)")
    args = parser.parse_args()

    report = run_health_check(board=args.board)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        # Human-readable output
        overall = report["overall"]
        icon = {"OK": "✅", "WARNING": "⚠️", "CRITICAL": "🚨"}.get(overall, "?")
        print(f"\n{icon} Kanban Health Check — {overall}")
        print(f"   Board: {report['board']}  |  DB: {report['db_path']}")
        print(f"   Tasks: {report['summary']['total_tasks']}  |  "
              f"Critical: {report['summary']['critical']}  |  "
              f"Warning: {report['summary']['warning']}")
        if report["summary"]["status_counts"]:
            counts = ", ".join(
                f"{k}={v}" for k, v in sorted(report["summary"]["status_counts"].items())
            )
            print(f"   Status: {counts}")
        print()

        for f in report["findings"]:
            if args.quiet and f.get("severity") == SEVERITY_OK:
                continue
            sev = f.get("severity", "?")
            icon_f = {"OK": "✓", "WARNING": "⚠", "CRITICAL": "✗"}.get(sev, "?")
            print(f"  {icon_f} [{sev}] {f.get('check', '?')}: {f.get('message', '')}")

        print()

    # Exit code
    if report["overall"] == SEVERITY_CRITICAL:
        sys.exit(1)
    elif report["overall"] == SEVERITY_WARNING:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
