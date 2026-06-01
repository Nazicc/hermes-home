#!/usr/bin/env python3
"""
Memory System Daily Self-Check
Exit codes: 0 = all ok, 1 = warnings, 2 = errors
"""
import json, subprocess, sys, os, time

CHECKS = []

def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))

def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, "", "binary not found"
    except subprocess.TimeoutExpired:
        return -1, "", "timed out"

def check_hindsight():
    rc, out, _ = run(["curl", "-sf", "http://127.0.0.1:18888/health"], timeout=5)
    if rc == 0:
        try:
            j = json.loads(out)
            ok = j.get("status") in ("ok", "healthy")
            check("Hindsight API", ok, f"status={j.get('status')}, db={j.get('database','?')}")
        except Exception:
            check("Hindsight API", False, "response not json")
    else:
        check("Hindsight API", False, f"not reachable (exit {rc})")

def check_simplemem():
    # Check SimpleMem MCP process
    rc, out, _ = run(["pgrep", "-f", "simplemem_mcp.py"])
    check("SimpleMem MCP process", rc == 0, "PID found" if rc == 0 else "not running")

    # Check Evolution process
    rc, out, _ = run(["pgrep", "-f", "simplemem_evolution_mcp.py"])
    check("SimpleMem Evolution process", rc == 0, "PID found" if rc == 0 else "not running")

def check_memory_storage():
    # Check SimpleMem/MemPalace storage at ~/.hermes/memories/
    mem_dir = os.path.expanduser("~/.hermes/memories")
    simplemem_dir = os.path.expanduser("~/.hermes/simplemem-data")
    evolution_dir = os.path.expanduser("~/.hermes/simplemem_evolution")

    for label, p in [("MemPalace memories", mem_dir), ("SimpleMem data", simplemem_dir), ("Evolution store", evolution_dir)]:
        if os.path.isdir(p):
            size = 0
            for dirpath, _, filenames in os.walk(p):
                for f in filenames:
                    try:
                        size += os.path.getsize(os.path.join(dirpath, f))
                    except OSError:
                        pass
            check(label, True, f"{size/1024:.0f} KB at {p}")
        else:
            check(label, True, "not present (non-critical, may use different backend)")

def check_hindsight_db():
    """Check Hindsight database stats"""
    rc, out, _ = run(["curl", "-sf", "http://127.0.0.1:18888/v1/default/banks/hermes-agent/stats"], timeout=5)
    if rc == 0:
        try:
            j = json.loads(out)
            nodes = j.get("total_nodes", "N/A")
            links = j.get("total_links", "N/A")
            docs = j.get("total_documents", "N/A")
            check("Hindsight DB", True, f"{nodes} nodes, {links} links, {docs} docs")
        except Exception:
            check("Hindsight DB", True, "stats ok but unparseable")
    else:
        check("Hindsight DB", True, "stats endpoint not available (non-critical)")

def main():
    check_hindsight()
    check_simplemem()
    check_memory_storage()
    check_hindsight_db()

    # Report
    errors = [c for c in CHECKS if not c[1]]
    warnings = [c for c in CHECKS if not c[1] and "non-critical" in c[2]]

    print("=== 🧠 Memory System Daily Self-Check ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    for name, ok, detail in CHECKS:
        icon = "✅" if ok else "⚠️" if "non-critical" in detail else "❌"
        print(f"  {icon} {name}: {detail}")

    print()
    if not errors:
        print("✅ All checks passed")
        sys.exit(0)
    elif all("non-critical" in c[2] for c in errors):
        print("⚠️  All pass, minor warnings only")
        sys.exit(1)
    else:
        print(f"❌ {len(errors)} check(s) failed")
        sys.exit(2)

if __name__ == "__main__":
    main()
