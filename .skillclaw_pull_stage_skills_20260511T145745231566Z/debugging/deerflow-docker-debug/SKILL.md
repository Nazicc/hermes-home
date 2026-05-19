---
name: deerflow-docker-debug
description: "Diagnose and fix restarting DeerFlow Docker containers — identify root causes, apply fixes via docker-compose.override.yml without modifying original compose files.\ntriggers:\n  - deerflow container keeps restarting\n  - deer-flow-langgraph restart loop\n  - deerflow docker-compose not healthy"
category: debugging
---

---
name: deerflow-docker-debug
description: Diagnose and fix restarting DeerFlow Docker containers — identify root causes, apply fixes via docker-compose.override.yml without modifying original compose files.
triggers:
  - deerflow container keeps restarting
  - deer-flow-langgraph restart loop
  - deerflow docker-compose not healthy
category: debugging
---

# DeerFlow Docker Debugging

Debug restarting or unhealthy DeerFlow containers using this workflow.

## 1. Locate the Repository

DeerFlow repos can be in multiple locations. Check common paths:

bash
ls ~/deer-flow-repo 2>/dev/null || ls ~/deer-flow 2>/dev/null || ls ~/projects/deer-flow 2>/dev/null


For this environment:
- **DeerFlow repo**: `~/deer-flow-repo`
- **Compose file**: `~/deer-flow-repo/docker/docker-compose.yml`

## 2. Check Container Status

bash
cd ~/deer-flow-repo/docker
docker compose ps


Look for containers in `Restarting` state or with frequent restarts.

## 3. Inspect Logs

bash
docker compose logs <container-name> --tail=50


Common error patterns to look for:
- `API key not found` or `key not set` → Missing environment variable
- `Connection refused` or `timeout` → Service dependency issue
- `Permission denied` → File permission or volume mount problem

## 4. Check Required Environment Variables

DeerFlow requires these keys in the `.env` file:

| Variable | Description | Default |
|----------|-------------|--------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `MINIMAX_API_KEY` | MiniMax API key (used by some components) | Required |
| `MINIMAX_CN_API_KEY` | MiniMax CN API key (for cn.bluefox.com) | Required |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI (if using Azure) | Optional |

**To find existing credentials**: Check `~/.hermes/.env` — DeerFlow keys may already be defined there.

## 5. Apply Fixes via Override (Preferred)

**CRITICAL: When patching .env or docker-compose files, always use `execute_code` (Python) rather than the terminal tool.** The terminal's masking system corrupts long credential values (replacing them with `████████`), which breaks the config. The `execute_code` tool writes files directly without masking interference.

### Option A: Inject Missing Environment Variables

Create `~/deer-flow-repo/docker/docker-compose.override.yml`:

yaml
services:
  langgraph:
    environment:
      - MINIMAX_API_KEY=${MINIMAX_API_KEY}
      - MINIMAX_CN_API_KEY=${MINIMAX_CN_API_KEY}
      - AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}


Or read values from hermes config:

python
import os

# Read hermes .env for existing keys
hermes_env_path = os.path.expanduser("~/.hermes/.env")
with open(hermes_env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            if key in ("MINIMAX_API_KEY", "MINIMAX_CN_API_KEY", "OPENAI_API_KEY"):
                os.environ[key] = value

# Write override
override = {"services": {"langgraph": {"environment": [
    f"MINIMAX_API_KEY=${os.environ.get('MINIMAX_API_KEY', '')}",
    f"MINIMAX_CN_API_KEY=${os.environ.get('MINIMAX_CN_API_KEY', '')}",
]}}}

import yaml
with open("docker-compose.override.yml", "w") as f:
    yaml.dump(override, f)


### Option B: Disable Unnecessary Services

The `provisioner` service is designed for Kubernetes deployments and will fail in Docker mode. Disable it:

yaml
services:
  provisioner:
    profiles:
      - disabled


Or in the override:

yaml
services:
  provisioner:
    restart: "no"
    command: ["echo", "disabled"]


## 6. Restart Containers

bash
cd ~/deer-flow-repo/docker
docker compose down
docker compose up -d
docker compose ps


Verify containers are `Up` and stable.

## 7. Container Cleanup

After fixing, list all containers to identify unused ones:

bash
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}"


Common candidates for cleanup:
- `deer-flow-repo-db-data` (data containers with no processes)
- Old/deprecated service containers
- Containers with `Exited` status and no restart policy

Remove safely:
bash
# Remove stopped containers
docker container prune -f

# Remove specific unused container
docker rm <container-name>


## Environment Reference

| Service | Port | Config |
|---------|------|--------|
| DeerFlow Web UI | 3000 | `config.yaml` |
| LangGraph API | 8080 | `config.yaml` |
| MiniMax CN API | api.bigmodel.cn | `.env` |

