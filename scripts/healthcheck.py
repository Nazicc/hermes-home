#!/usr/bin/env python3
"""
Unified Health Check for SkillClaw + Hermes Agent stack.
Reports all service statuses in a compact format.
Exit code: 0 = all healthy, 1 = degraded, 2 = critical failure.

Usage:
  python3 healthcheck.py              # Full check (default)
  python3 healthcheck.py --brief      # One-liner summary
  python3 healthcheck.py --json       # Machine-readable JSON
  python3 healthcheck.py --watch      # Watch mode (every 10s)
"""
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Callable

SKILLCLAW_PORT = 30000
GATEWAY_PORT = 8642
SKILLCLAW_DIR = os.path.expanduser("~/.skillclaw")
HERMES_DIR = os.path.expanduser("~/.hermes")
LAUNCH_AGENTS = os.path.expanduser("~/Library/LaunchAgents")
# LaunchAgent labels for all managed services
MANAGED_SERVICES = {
    "skillclaw-proxy":  "com.hermes.skillclaw",
    "skillclaw-evolve": "ai.hermes.skillclaw-evolve",
    "skillclaw-key":    "com.hermes.skillclaw-key-reloader",
    "gateway":          "ai.hermes.gateway",
    "logrotate":        "ai.hermes.logrotate",
    "bridge-sync":      "ai.hermes.bridge-sync",
}


@dataclass
class CheckResult:
    name: str
    status: str  # ✓ ok | ⚠ warn | ✗ fail | - skip
    detail: str = ""
    exit_weight: int = 1  # 0=info, 1=degraded, 2=critical


@dataclass
class HealthReport:
    results: list = field(default_factory=list)
    failures: list = field(default_factory=list)

    def add(self, name, status, detail="", exit_weight=1):
        r = CheckResult(name, status, detail, exit_weight)
        self.results.append(r)
        if status in ("✗", "✗ fail"):
            self.failures.append(r)
        return r

    def exit_code(self):
        weights = {r.exit_weight for r in self.failures}
        return 2 if 2 in weights else (1 if self.failures else 0)

    def summary(self):
        total = len(self.results)
        ok = sum(1 for r in self.results if r.status in ("✓", "✓ ok", "- skip"))
        fail = len(self.failures)
        warn = total - ok - fail
        return total, ok, warn, fail

    def to_dict(self):
        return {
            "summary": {"total": len(self.results), "ok": self.summary()[1], "warn": self.summary()[2], "fail": self.summary()[3]},
            "exit_code": self.exit_code(),
            "checks": [{"name": r.name, "status": self._clean_status(r.status), "detail": r.detail} for r in self.results],
        }

    @staticmethod
    def _clean_status(s: str):
        return s.replace("✓ ", "").replace("✗ ", "").replace("⚠ ", "").replace("- ", "")

    def print_pretty(self):
        total, ok, warn, fail = self.summary()
        print(f"\n{'='*50}")
        print(f"  🔍 Hermes + SkillClaw 健康检查")
        print(f"{'='*50}")
        for r in self.results:
            icon = r.status[:1]
            name_pad = r.name.ljust(28)
            if r.status == "✗ fail":
                print(f"  {icon} {name_pad} {r.detail}")
            elif r.status == "⚠ warn":
                print(f"  {icon} {name_pad} {r.detail}")
            elif r.status == "- skip":
                continue
            else:
                print(f"  {icon} {name_pad} {r.detail}")
        icon = "✅" if fail == 0 else ("⚠️" if warn > 0 else "❌")
        print(f"\n  {icon} {ok}/{total} checks passed", end="")
        if fail:
            print(f"  ({fail} failed)", end="")
        if warn:
            print(f"  ({warn} warnings)", end="")
        print(f"\n{'='*50}\n")

    def print_brief(self):
        total, ok, warn, fail = self.summary()
        icon = "✅" if fail == 0 else ("⚠️" if warn > 0 else "❌")
        parts = [icon]
        for r in self.results:
            if r.status == "✗ fail":
                parts.append(f"✗{r.name}:{r.detail.split(chr(10))[0]}")
            elif r.status == "⚠ warn":
                parts.append(f"⚠{r.name}:{r.detail.split(chr(10))[0]}")
        if len(parts) == 1:
            print(f"{icon} All {ok}/{total} healthy")
        else:
            print(" | ".join(parts))

    def print_json(self):
        print(json.dumps(self.to_dict(), indent=2))


# === Check functions ===

def check_process(report: HealthReport, label: str, friendly: str, warn_on_missing: bool = False) -> None:
    """Check if a launchd-managed process is running.
    If warn_on_missing=True, report as warning instead of fail when not loaded."""
    try:
        result = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True, text=True, timeout=5,
        )
        out = result.stdout.strip()
        if not out or "Could not find service" in out:
            status = "⚠ warn" if warn_on_missing else "✗ fail"
            report.add(f"{friendly}", status, f"launchd: {label} not loaded")
            return
        # macOS launchctl list outputs OpenStep plist format
        # Parse for PID and LastExitStatus
        import re
        pid_match = re.search(r'"PID"\s*=\s*(\d+)', out)
        exit_match = re.search(r'"LastExitStatus"\s*=\s*(-?\d+)', out)
        if pid_match:
            pid = int(pid_match.group(1))
            exit_code = int(exit_match.group(1)) if exit_match else 0  # type: ignore[arg-type]
            # macOS LastExitStatus = signal number (positive) for killed processes.
            # PID exists → process is alive → OK, note exit for context.
            note = f"PID {pid}"
            if exit_code != 0:
                note += f" (prev exit: {exit_code})"
            report.add(f"{friendly}", "✓ ok", note)
        elif exit_match:
            exit_code = int(exit_match.group(1))
            if exit_code == 0:
                # One-shot service that completed successfully
                report.add(f"{friendly}", "- skip", "loaded (exited 0)")
            else:
                report.add(f"{friendly}", "✗ fail", f"exited ({exit_code})")
        else:
            report.add(f"{friendly}", "⚠ warn", f"unexpected output")
    except subprocess.TimeoutExpired:
        report.add(f"{friendly}", "⚠ warn", f"launchctl timeout")
    except Exception as e:
        report.add(f"{friendly}", "⚠ warn", str(e))


def check_http(report, name: str, url: str, expected_status: int = 200,
               timeout: float = 5.0, check_content=None) -> None:
    """Check HTTP endpoint health."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            if status != expected_status:
                report.add(name, "✗ fail", f"HTTP {status} (expected {expected_status})")
                return
            if check_content is not None:
                body = resp.read().decode("utf-8", errors="replace")[:200]
                check_content(body, report, name)
            else:
                report.add(name, "✓ ok", f"HTTP {status}")
    except urllib.error.HTTPError as e:
        report.add(name, "✗ fail", f"HTTP {e.code}")
    except urllib.error.URLError as e:
        report.add(name, "✗ fail", f"connection failed: {e.reason}")
    except Exception as e:
        report.add(name, "⚠ warn", str(e))


def check_port(report: HealthReport, name: str, port: int, pid: int | None = None) -> None:
    """Check if a port is listening."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-P"],
            capture_output=True, text=True, timeout=5,
        )
        if "LISTEN" in result.stdout:
            lines = [l for l in result.stdout.split("\n") if "LISTEN" in l]
            pids_found = set()
            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    pids_found.add(int(parts[1]))
            detail = f"port {port}"
            if pid and pid in pids_found:
                detail += f" (PID {pid})"
            elif pids_found:
                detail += f" (PIDs: {', '.join(map(str, pids_found))})"
            report.add(name, "✓ ok" if (not pid or pid in pids_found) else "⚠ warn", detail)
        else:
            report.add(name, "✗ fail", f"port {port} not listening")
    except Exception as e:
        report.add(name, "⚠ warn", str(e))


def check_disk(report: HealthReport, path: str, name: str, warn_mb: int = 100, fail_mb: int = 500) -> None:
    """Check log directory size."""
    try:
        result = subprocess.run(
            ["du", "-sm", path],
            capture_output=True, text=True, timeout=5,
        )
        size_mb = int(result.stdout.split("\t")[0])
        if size_mb >= fail_mb:
            report.add(name, "✗ fail", f"{size_mb}MB (threshold: {fail_mb}MB)")
        elif size_mb >= warn_mb:
            report.add(name, "⚠ warn", f"{size_mb}MB (threshold: {warn_mb}MB)")
        else:
            report.add(name, "✓ ok", f"{size_mb}MB")
    except Exception:
        report.add(name, "- skip", "no logs dir")


def main():
    args = set(sys.argv[1:])
    brief = "--brief" in args
    json_out = "--json" in args
    watch = "--watch" in args

    if watch:
        brief = True  # watch mode uses compact output
        try:
            while True:
                r = run_checks()
                r.print_brief()
                time.sleep(10)
        except KeyboardInterrupt:
            print("\nStopped.")
            return

    r = run_checks()

    if json_out:
        r.print_json()
    elif brief:
        r.print_brief()
    else:
        r.print_pretty()

    sys.exit(r.exit_code())


def run_checks() -> HealthReport:
    report = HealthReport()

    # 1. Process status (launchd)
    for friendly, label in MANAGED_SERVICES.items():
        warn = (friendly == "gateway")  # gateway may run ad-hoc outside launchd
        check_process(report, label, friendly, warn_on_missing=warn)

    # 2. Port checks
    check_port(report, "port 30000 (proxy)", 30000)
    check_port(report, "port 8642 (gateway)", 8642)

    # 3. HTTP health endpoints
    def check_proxy_models(body, report, name):
        if '"deepseek' in body.lower() or '"model"' in body:
            report.add(name, "✓ ok", f"LLM model available")
        else:
            report.add(name, "⚠ warn", f"unexpected response: {body[:80]}")

    check_http(report, "proxy /healthz", f"http://localhost:{SKILLCLAW_PORT}/healthz")
    check_http(report, "proxy /v1/models", f"http://localhost:{SKILLCLAW_PORT}/v1/models",
               check_content=check_proxy_models)
    check_http(report, "gateway /health", f"http://localhost:{GATEWAY_PORT}/health")

    # 4. Disk usage
    check_disk(report, SKILLCLAW_DIR + "/logs", "skillclaw logs")
    check_disk(report, HERMES_DIR + "/logs", "hermes logs")

    # 5. Plist file integrity
    for friendly, label in MANAGED_SERVICES.items():
        plist_path = os.path.join(LAUNCH_AGENTS, f"{label}.plist")
        if os.path.exists(plist_path):
            pass  # referenced in process check
        else:
            report.add(f"plist:{friendly}", "⚠ warn", f"missing: {plist_path}")

    return report


if __name__ == "__main__":
    main()
