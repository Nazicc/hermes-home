---
name: coze-studio
description: "Execute a coze-studio (opencoze/open-coze open-source) Agent as a sub-agent via its local HTTP API. Use when you need to offload a task to a coze-studio Agent (NOT a Workflow — coze-studio open-source does not have Workflows). NOT for: coze.cn cloud API, non-HTTP integrations, or modifying coze-studio source code."
category: general
---

## coze-studio Integration

**Goal**: Invoke a coze-studio (opencoze/open-coze) Agent as a sub-agent without modifying coze-studio source code, preserving upgrade compatibility.

**Framework**: coze-studio open-source has **Agents** (not Workflows). Workflows exist only in coze.cn cloud.

---

## Prerequisites

1. coze-studio is running locally (e.g., via `uv run coze-studio` or installed package).
2. The Agent you want to call has already been created via the coze-studio UI.
3. You have the Agent ID (visible in the coze-studio UI when editing the Agent).

---

## API Base


http://localhost:8000


The port is `8000` by default. Verify with:
bash
lsof -i :8000 | grep LISTEN


---

## Execute an Agent (Chat)

**Endpoint**: `POST /v3/chat`

**Headers**:

Authorization: Bearer <token>
Content-Type: application/json


**Request Body** (MessageCreateRequest schema):

{
  "stream": false,
  "tokens": -1,
  "model": "<agent-id>",
  "messages": [
    {
      "role": "user",
      "content": "<task prompt>"
    }
  ]
}


| Field | Notes |
|---|---|
| `model` | Must be the Agent ID string, NOT a model name like `gpt-4o` |
| `stream` | Set to `false` for a single complete response |
| `tokens` | `-1` means no token limit |
| `messages[].role` | Use `"user"` for user messages |

**Python bridge example**:
python
import requests

def execute_coze_agent(agent_id: str, task: str, base_url: str = "http://localhost:8000", token: str = "") -> str:
    """
    Execute a coze-studio Agent and return the text response.
    """
    response = requests.post(
        f"{base_url}/v3/chat",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "stream": False,
            "tokens": -1,
            "model": agent_id,
            "messages": [{"role": "user", "content": task}],
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    # Extract assistant message
    messages = data.get("messages", [])
    for msg in messages:
        if msg.get("role") == "assistant":
            return msg.get("content", "")
    return ""


---

## Response Parsing

The `/v3/chat` response is a JSON object. Extract the assistant's reply from:
python
messages = response_data.get("messages", [])
assistant_text = next((m["content"] for m in messages if m["role"] == "assistant"), "")


**Common errors**:
- `messages` array is empty → Agent returned no content. Check if the task prompt is clear and the Agent is properly configured.
- HTTP 401/403 → Missing or invalid Authorization token. Ensure `Bearer <token>` header is set.
- HTTP 404 → Wrong endpoint. Use `/v3/chat`, NOT `/v1/chat/completions` (that is an OpenAI-compatible endpoint, not the coze agent endpoint).

---

## Key Constraints

1. **Do NOT modify coze-studio source code** — all integration is external via HTTP API.
2. **Agent ID is required** — not a model name. Find it in the coze-studio UI.
3. **Workflows do not exist in opencoze** — if you need a workflow-like pattern, chain multiple Agent calls in sequence.
4. **No streaming needed for sub-agent use** — set `"stream": false` and parse the complete response.

---

## Health Check

Verify coze-studio is reachable:
bash
curl -s http://localhost:8000/health || echo "NOT RUNNING"


If not running, start it:
bash
cd /path/to/open-coze && uv run coze-studio


