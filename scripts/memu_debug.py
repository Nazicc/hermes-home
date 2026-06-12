#!/usr/bin/env python3
"""Temporary debug script - prints MEMU_DATABASE_URL env var and exits."""
import os, json
with open("/tmp/memu_env_debug.json", "w") as f:
    json.dump({
        "MEMU_DATABASE_URL": os.environ.get("MEMU_DATABASE_URL", "NOT SET"),
        "MEMU_MCP_PORT": os.environ.get("MEMU_MCP_PORT", "NOT SET"),
        "MEMU_EMBEDDING_API_KEY": "SET" if os.environ.get("MEMU_EMBEDDING_API_KEY") else "NOT SET",
        "MEMU_LLM_API_KEY": "SET" if os.environ.get("MEMU_LLM_API_KEY") else "NOT SET",
        "MEMU_EMBEDDING_MODEL": os.environ.get("MEMU_EMBEDDING_MODEL", "NOT SET"),
    }, f, indent=2)
print(json.dumps(json.load(open("/tmp/memu_env_debug.json")), indent=2))
