---
name: deepevil-mcp
description: "DeepCode (port 8000) and DeepTutor (port 8001) MCP server integration. Use when calling DeepCode planning/requirements/code tools or DeepTutor knowledge/Q&A tools via MCP within the hermes-agent workflow. Covers code synthesis, paper-to-code, workflow orchestration, knowledge RAG, tutoring, Co-Writer, notebook, and Q&A. NOT for DeerFlow (port 1933) — a separate skill. NOT for tasks that only need REST APIs directly or for simple file I/O, basic arithmetic, or non-code topics."
category: general
---

# DeepCode + DeepTutor MCP Integration

## Quick Reference

### Python Interpreter
Always use `/Users/can/.openharness-venv/bin/python` — same venv as DeepCode/DeepTutor services, has both `mcp` and `httpx` packages.

### REST API Endpoints
- DeepCode: `http://127.0.0.1:8000`
- DeepTutor: `http://127.0.0.1:8001`

### MCP Server Files
- DeepCode MCP: `/Users/can/.hermes/deepcode-mcp/deepcode_mcp.py`
- DeepTutor MCP: `/Users/can/.hermes/deeptutor-mcp/deeptutor_mcp.py`

## DeepCode Tools (9 total)

| Tool | Description |
|------|-------------|
| `deepcode_chat_planning` | 任务规划聊天 |
| `deepcode_paper_to_code` | 论文转代码 |
| `deepcode_workflow_status` | 查询任务状态 |
| `deepcode_workflow_respond` | 发送后续输入 |
| `deepcode_requirements_questions` | 需求澄清提问 |
| `deepcode_requirements_summarize` | 需求摘要 |
| `deepcode_active_workflows` | 活跃任务列表 |
| `deepcode_recent_workflows` | 最近任务列表 |
| `deepcode_health` | 健康检查 |

## DeepTutor Tools (23 total)

- `deeptutor_health`, `deeptutor_runtime_topology`
- `deeptutor_knowledge_base_*` — 知识库相关
- `deeptutor_tutorbot_*` — TutorBot 模块
- `deeptutor_cowriter_*` — Co-Writer 模块
- `deeptutor_book_*` — Book 模块
- `deeptutor_notebook_*` — Notebook 模块
- `deeptutor_qa_*` — 问答模块

## config.yaml Registration

Add to `mcp_servers:` section (after the `deerflow:` block around line 389):

yaml
deepcode:
  command: /Users/can/.openharness-venv/bin/python
  args:
    - /Users/can/.hermes/deepcode-mcp/deepcode_mcp.py
  env:
    DEEPCODE_BASE_URL: http://127.0.0.1:8000
  enabled: true
deeptutor:
  command: /Users/can/.openharness-venv/bin/python
  args:
    - /Users/can/.hermes/deeptutor-mcp/deeptutor_mcp.py
  env:
    DEEPTUTOR_BASE_URL: http://127.0.0.1:8001
  enabled: true


> **Note**: `config.yaml` is in `.gitignore` — entries must be added manually and will not be tracked by git.

## Smoke Testing MCP Servers

Use `asyncio.create_subprocess_exec` (NOT `subprocess.Popen` with echo piping):

python
import asyncio, json

async def test_mcp_server(script_path, tool_name, params=None):
    proc = await asyncio.create_subprocess_exec(
        '/Users/can/.openharness-venv/bin/python', script_path,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Initialize (required MCP handshake)
    init_msg = {
        'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
        'params': {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {'name': 'test', 'version': '1.0'}
        }
    }
    await proc.stdin.write((json.dumps(init_msg) + '\n').encode())
    await proc.stdin.drain()
    await asyncio.wait_for(proc.stdout.readline(), timeout=5)

    # Send notifications/initialized before calling tools
    await proc.stdin.write(
        (json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized', 'params': {}}) + '\n').encode()
    )
    await proc.stdin.drain()

    # Call tool
    tool_msg = {
        'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
        'params': {'name': tool_name, 'arguments': params or {}}
    }
    await proc.stdin.write((json.dumps(tool_msg) + '\n').encode())
    await proc.stdin.drain()
    tool_resp = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
    await proc.terminate()
    return json.loads(tool_resp)


**Why echo piping fails**: MCP uses async request/response multiplexing over stdin/stdout. The initialize response arrives immediately; simple echo-based approaches cannot demultiplex responses by id and cannot send the required `notifications/initialized` notification before calling tools.

## Health Check (Cron Mode)

A lightweight health check that verifies both REST APIs respond without errors. Returns `[SILENT]` if all checks pass.

## Deployment

See `deepcode-mcp/DEPLOYMENT_NOTES.md` for detailed deployment instructions.
