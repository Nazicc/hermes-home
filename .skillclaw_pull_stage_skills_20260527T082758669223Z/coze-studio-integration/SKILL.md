---
name: coze-studio-integration
description: "Use coze-studio (coze-dev/coze-studio or opencoze/open-coze, self-hosted) as a sub-agent executor or workflow execution engine via its HTTP API. Covers PAT authentication, workflow execution, agent chat, file-queue bridge setup, and common failure modes. Triggered when tasks should be offloaded to coze-studio, when coze-studio API integration is needed, or when debugging coze-studio authentication issues. NOT for: ByteDance Coze Bot platform (commercial), creating coze-studio workflows (use the Web UI), debugging coze-studio deployment issues."
category: general
---

# coze-studio Integration

Use coze-studio as a sub-agent executor or workflow execution engine. coze-studio is a self-hosted Coze platform deployed as Docker containers.

## Architecture

Use a **file-based job queue with polling** for reliable decoupling:

1. Write a job JSON file to a shared location
2. Call coze-studio's workflow or chat endpoint
3. Poll the retrieve endpoint until status is `success` or `failed`
4. Read the result from the job file or API response

## Deployment Quick-Check

Always confirm the deployment is healthy first:

bash
docker ps --filter name=coze- --format "table {{.Names}}\t{{.Status}}"


Expected: 12 containers running, including `coze-server`, `coze-web`, `mysql`, `redis`, `nsqd`, `nsqlookupd`, `elasticsearch`, `milvus`, `minio`.

If containers are not running:
bash
cd ~/coze-studio/docker && docker compose up -d


- **Base path**: `~/.coze-studio/` or `~/.opencoze/`
- **Default ports**: 8888 (coze-dev/coze-studio) or 8000 (opencoze/open-coze)
- **Health check**: `curl -s http://localhost:<port>/`

## Authentication

coze-studio uses a Personal Access Token (PAT) for API access. Two creation methods exist depending on your version:

### Method 1 — Web UI (coze-dev/coze-studio)

**Step 1**: Log into the Web UI at `http://localhost:8888`, navigate to Settings → Personal Access Tokens, generate a token.

**Step 2**: Use the PAT as Bearer token:
bash
curl -X POST http://localhost:8888/v1/workflows/chat \
  -H "Authorization: Bearer <PAT>" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id":"...","workflow_data":{"parameters":{...}}}'


> ⚠️ **Bootstrapping constraint**: The PAT creation endpoint requires a Web UI session cookie — it cannot be called programmatically without first logging in through the browser. **PAT tokens must be pre-generated manually via the Web UI before any automated API calls.**

### Method 2 — MySQL (opencoze/open-coze)

If the web UI PAT creation doesn't work, inject PAT directly into MySQL:

bash
# Find MySQL credentials
docker ps --format '{{.Names}}' | grep coze
docker inspect <container-name> | grep -A5 MYSQL
# Or check:
cat ~/.opencoze/docker-compose.yml 2>/dev/null || find ~/.opencoze -name '*.yml' -o -name '*.env'

# Connect and create PAT
mysql -h <host> -P <port> -u <user> -p<password> <db-name>

-- Find existing PAT
SELECT id, name, token FROM personal_access_token LIMIT 5;

-- Create a new PAT (if none exist)
INSERT INTO personal_access_token (id, name, token, expires_at, created_at, updated_at)
VALUES (1, 'hermes-integration', '<16-char-token>', '2099-12-31 23:59:59', NOW(), NOW());


### Get Agent and Bot IDs

sql
SELECT id, name FROM agent;
SELECT id, name, system_prompt FROM bot;


## Critical: system_prompt in `bot` table

**The most common reason coze-studio returns empty messages is an empty `system_prompt` in the `bot` table.**

The `system_prompt` field overrides API parameters. If NULL or empty, the agent returns no content:

sql
UPDATE bot SET system_prompt = 'You are a helpful assistant.' WHERE id = <bot-id>;

-- Verify
SELECT id, name, system_prompt FROM bot WHERE id = <bot-id>;


## API Reference

### Workflow Execution

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/v1/workflows/chat` | PAT Bearer | Execute a workflow |
| GET | `/v1/workflows/chat/retrieve` | PAT Bearer | Retrieve workflow run result |
| GET | `/api/v1/workflow/list` | PAT Bearer | List available workflows |
| GET | `/api/v1/workflow/apiDetail` | PAT Bearer | Get workflow details |
| POST | `/api/v1/workflow/cancel` | PAT Bearer | Cancel a workflow run |

**Request format**:

{
  "workflow_id": "<workflow_id>",
  "workflow_data": {
    "parameters": { "key": "value" }
  },
  "conversation_id": "<optional-uuid>",
  "stream": false
}


**Execute**:
bash
curl -X POST http://localhost:<port>/v1/workflows/chat \
  -H "Authorization: Bearer <PAT>" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id":"<id>","workflow_data":{"parameters":{...}}}'


**Workflow Discovery**:
bash
curl -s http://localhost:8888/api/v1/workflow/list \
  -H "Authorization: Bearer $COZE_PAT" | python3 -m json.tool


### Agent / Chat

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/v3/chat` | PAT Bearer | Start agent conversation |
| GET | `/v3/chat/retrieve` | PAT Bearer | Retrieve chat result |

**Start chat**:
bash
curl -X POST http://localhost:<port>/v3/chat \
  -H "Authorization: Bearer <PAT>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "<agent-id>",
    "user_id": "test-user",
    "stream": false,
    "auto_save_history": true,
    "messages": [{"role": "user", "content": "<prompt>"}]
  }'


**Response**:

{
  "code": 0,
  "msg": "success",
  "data": {
    "conversation_id": "<conv-id>",
    "id": "<chat-id>"
  }
}


**Retrieve result**:
bash
curl -G http://localhost:<port>/v3/chat/retrieve \
  --data-urlencode "chat_id=<chat-id>" \
  --data-urlencode "conversation_id=<conversation-id>" \
  -H "Authorization: Bearer <PAT>"


## Bridge Script

python
#!/usr/bin/env python3
"""coze-studio bridge — file-based job queue with polling."""
import json
import time
import requests
import uuid
import sys
import os
from pathlib import Path

COZE_API = os.environ.get("COZE_BASE_URL", "http://localhost:8888")
PAT = os.environ.get("COZE_PAT", "")
JOB_DIR = Path(os.environ.get("COZE_JOB_DIR", "/tmp/coze-jobs"))
JOB_DIR.mkdir(exist_ok=True)

def submit_job(prompt: str, agent_id: str, endpoint: str = "/v3/chat") -> dict:
    """Submit a job and return the job state."""
    job_id = str(uuid.uuid4())
    
    resp = requests.post(
        f"{COZE_API}{endpoint}",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json={
            "agent_id": agent_id,
            "user_id": "hermes",
            "stream": False,
            "auto_save_history": True,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=30
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    
    return {"job_id": job_id, "chat_id": data["id"],
            "conversation_id": data["conversation_id"]}

def poll_result(state: dict, max_wait: int = 120) -> str:
    """Poll until success/failed, return assistant message content."""
    start = time.time()
    
    while time.time() - start < max_wait:
        resp = requests.get(
            f"{COZE_API}/v3/chat/retrieve",
            params={"chat_id": state["chat_id"],
                    "conversation_id": state["conversation_id"]},
            headers={"Authorization": f"Bearer {PAT}"},
            timeout=15
        )
        resp.raise_for_status()
        result = resp.json()["data"]
        
        if result["status"] == "success":
            for msg in result.get("messages", []):
                if msg.get("role") == "assistant" and msg.get("content"):
                    return msg["content"]
            return "[no assistant message in response]"
        
        if result["status"] == "failed":
            return f"[coze-studio error: {result.get('last_error', 'unknown')}]"
        
        time.sleep(2)
    
    return "[timeout waiting for coze-studio response]"

if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Hello"
    agent_id = sys.argv[2] if len(sys.argv) > 2 else "<agent-id>"
    
    state = submit_job(prompt, agent_id)
    result = poll_result(state)
    print(result)


## Integration Patterns

### Pattern A — File Queue (Recommended)

Best for reliability and decoupling. Hermes never touches coze API directly.


Hermes writes job → bridge process polls → calls coze API → writes result


**Setup**:
bash
mkdir -p ~/coze-jobs/in ~/coze-jobs/out ~/coze-jobs/done


**Bridge** (runs as a sidecar):
python
import os, json, glob, time
import requests

COZE_BASE = os.environ["COZE_BASE_URL"]
PAT = os.environ["COZE_PAT"]
HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

while True:
    for job_file in sorted(glob.glob("/path/to/in/*.json")):
        job = json.load(open(job_file))
        out_file = job_file.replace("/in/", "/out/")

        resp = requests.post(
            f"{COZE_BASE}/v1/workflows/chat",
            headers=HEADERS,
            json={"workflow_id": job["workflow_id"], "workflow_data": {"parameters": job.get("parameters", {})}}}
        )
        result = resp.json()

        with open(out_file, "w") as f:
            json.dump({"job_id": job["job_id"], "result": result}, f)

        os.rename(job_file, job_file.replace("/in/", "/done/"))
    time.sleep(2)


### Pattern B — Direct HTTP

Hermes calls coze API directly. For blocking execution:

**Non-streaming**:
bash
curl -X POST http://localhost:<port>/v1/workflows/chat \
  -H "Authorization: Bearer $COZE_PAT" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id":"<id>","workflow_data":{"parameters":{...}}}'


**Streaming** (SSE):
bash
curl -s -N http://localhost:8888/v1/workflows/chat \
  -H "Authorization: Bearer $COZE_PAT" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id":"<id>","workflow_data":{"parameters":{...}},"stream":true}'


⚠️ Streaming requires parsing SSE line-by-line; prefer file queue for multi-step pipelines.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `{"code": 10003, "msg": "invalid token"}` | PAT not in DB | Insert via MySQL or create via Web UI |
| `700012006 missing authorization in header` | API called without Bearer token | Add `Authorization: Bearer <PAT>` header |
| `401 missing session_key in cookie` | PAT creation or workflow list endpoint called without Web UI session | Use Web UI for PAT creation, pre-know workflow_id |
| Empty `content` in assistant message | Empty `system_prompt` in `bot` table | `UPDATE bot SET system_prompt = '...' WHERE id = <bot-id>` |
| `{"code": 10002, ...}` | Wrong agent_id or bot not enabled | Check `agent` and `bot` tables |
| `{"code": 1000001, ...}` | Invalid workflow_id | Verify via `/api/v1/workflow/list` |
| Connection refused | coze-studio not running | `docker compose up -d` or `docker start` |
| 404 on `/v1/workflows` (older versions) | Endpoint doesn't exist in opencoze | Use `/v3/chat` instead |
| Middleware returns no error | Router middleware stubs — auth checks inside handlers | Always check JSON response body for errors |

## Environment Variables

bash
export COZE_PAT="your-pat-token-here"
export COZE_BASE_URL="http://localhost:8888"  # or http://localhost:8000
export COZE_JOB_DIR="/tmp/coze-jobs"


## Source Code

- Backend: `~/coze-studio/backend/` (Go)
- Docker: `~/coze-studio/docker/`
- Config: `~/coze-studio/docker/.env`
- Key handler: `backend/api/handler/coze/agent_run_service.go` (ChatV3 handler)
- Middleware stubs: `backend/api/router/coze/middleware.go` (all return nil — auth is in-handler)
