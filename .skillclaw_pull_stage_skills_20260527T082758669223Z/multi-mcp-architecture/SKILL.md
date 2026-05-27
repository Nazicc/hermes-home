---
name: multi-mcp-architecture
description: "Diagnose multi-MCP system architecture — disambiguate DeerFlow/DeepCode/DeepTutor call chains, API key locations, and endpoint configuration differences. Use when: you need to understand how multiple MCP servers relate to each other, you encounter two different \"DeepCode\" services and need to know which is which, or you need to trace where sub-agents get their API keys. NOT for: MCP crash debugging (use mcp-debugging instead), DeerFlow-only integration (use deerflow-mcp-integration instead)."
category: general
---

# Multi-MCP 架构诊断方法

## 核心原则

**关键发现：同时存在多个 "DeepCode" 相关进程，必须区分清楚，否则会混淆调试方向。**

| 概念 | 端口 | 协议 | 用途 |
|------|------|------|------|
| DeerFlow 内部的 DeepCode MCP Server | :8000 | MCP (via mcp-client-python) | DeerFlow 的代码搜索 MCP |
| ~/DeepCode agent framework | :8001 | Agent Framework HTTP | 独立 DeepCode Agent |
| DeepTutor MCP | :8090 | MCP | DeerFlow 的教育辅导 MCP |

**三个 sub-agent 各自独立调用 MiniMax API，没有统一的 orchestration gateway。**

DeerFlow 是主控 Agent，DeepCode 和 DeepTutor 是其两个工具子 Agent，通过 DeerFlow 统一调度。

## 端点与健康检查

| 服务 | 健康检查端点 | 配置来源 |
|------|-------------|---------|
| DeerFlow (MCP Server) | http://localhost:8000/health | deerflow_mcp.py 中的 MCPServer |
| DeepCode MCP | http://localhost:8000/mcp (via DeerFlow) | mcp_server.py 中的 MCP 协议端点 |
| DeepCode Agent | http://localhost:8001/health | ~/DeepCode/agent/framework.py |
| DeepTutor MCP | http://localhost:8090/health | deerflow/components/deeptutor_mcp.py |

**端口分配参考：**
- `:8000` — deepcode-mcp（DeerFlow 项目内）
- `:8001` — 独立 DeepCode Agent 框架
- `:8080` — DeerFlow 主服务（如有）
- `:8090` — DeepTutor MCP

## 诊断步骤

### Step 1：确认有哪些 MCP server 在运行

bash
# 方法 A：查 DeerFlow 项目的 MCP 配置
cat ~/.DeerFlow/config.yaml

# 方法 B：直接 hit 健康检查端点
curl http://localhost:8000/health      # deepcode-mcp server
curl http://localhost:8001/health      # 独立 DeepCode Agent
curl http://localhost:8090/health      # DeepTutor MCP

# 方法 C：查进程
lsof -i :8000 -i :8001 -i :8090
ps aux | grep -i "deepcode\|deerflow" | grep -v grep


### Step 2：确认 MiniMax API Key 位置

MiniMax API key 在各 sub-agent 的 config 中独立配置：

| Agent | Key 位置 | 环境变量 |
|-------|---------|---------|
| DeerFlow | `~/.DeerFlow/config.yaml` 或项目根目录 `.env` | DEERFLOW_MINIMAX_API_KEY |
| DeepCode | `~/DeepCode/config.py` 或 `~/DeepCode/.env` | MINIMAX_API_KEY |
| DeepTutor | DeerFlow 目录 `.env` | DEEPTUTOR_MINIMAX_API_KEY |

各子 Agent 的 key 是独立的，不能混用。

**API 端点格式**：`https://api.minimax.chat/v1/text/chatcompletion_v2`

### Step 3：追踪调用链

**DeerFlow MCP server (:8000) 的调用流程：**


DeerFlow UI → DeerFlow backend → deepcode-mcp (:8000) → 本地工具执行
                                      ↓
                              （不直接调 MiniMax）


**三个 sub-agent 的 MiniMax 调用互相独立：**


DeerFlow sub-agent ──────→ MiniMax API (直接调用)
DeepCode sub-agent ──────→ MiniMax API (直接调用)
DeepTutor sub-agent ─────→ MiniMax API (直接调用)


### Step 4：检查配置文件

bash
# 查看 DeerFlow 的 MCP 客户端配置
cat deerflow/mcp/deerflow_mcp.py  # 确认 DeerFlow 连接的是哪个端口

# 检查 DeepTutor MCP 是否正常加载
cat deerflow/components/deeptutor_mcp.py  # 确认 MCP server 的初始化和端口绑定

# 查看 API Key 环境变量加载
grep -r "load_dotenv\|os.getenv" deerflow/


### Step 5：区分 DeepCode 的两个实体

- 如果请求经过 DeerFlow 的 MCP 客户端 → 走 :8000（DeerFlow 内置 DeepCode）
- 如果请求直接发往 :8001 → 走 ~/DeepCode agent framework

## 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|---------|
| DeerFlow 报 "MCP connection failed" | DeerFlow MCP Server 未启动 | 重启 deerflow_mcp.py |
| DeepCode 返回 401 | DeepCode Agent 的 API key 过期或为空 | 更新 ~/DeepCode/.env |
| DeepTutor 无响应 | :8090 端口未监听 | 检查 deeptutor_mcp.py 是否正常启动 |
| 两个 DeepCode 混淆 | 没区分 MCP (:8000) 和 Agent (:8001) | 参考端口区分表格 |
| 所有子 agent 都通过 DeerFlow 走统一网关 | 误解 | 否，各自独立调用 MiniMax |
| MCP server 持有 MiniMax key | 误解 | 否，key 在各 sub-agent 的 config 中 |

## 常见混淆陷阱

| 混淆点 | 真相 |
|--------|------|
| "DeepCode MCP" 和 "DeepCode Agent" | MCP 是 :8000 的服务；Agent 是 ~/DeepCode 目录的独立程序 |
| 所有子 agent 都通过 DeerFlow 走统一网关 | 否，各自独立调用 MiniMax |
| MCP server 持有 MiniMax key | 否，key 在各 sub-agent 的 config 中 |

## 快速验证命令

bash
# 确认 deepcode-mcp 是否在运行
curl -s http://localhost:8000/health | head -c 200

# 确认 DeerFlow 项目 config
cat ~/.DeerFlow/config.yaml 2>/dev/null | grep -i minimax | head -5

# 查看运行中的 Python 进程
ps aux | grep -i "deepcode\|deerflow" | grep -v grep


## 文件位置速查

| 文件 | 路径 | 作用 |
|------|------|------|
| deerflow_mcp.py | deerflow/mcp/deerflow_mcp.py | DeerFlow MCP 客户端入口 |
| mcp_server.py | deerflow/mcp/mcp_server.py | MCP 协议服务端 |
| deeptutor_mcp.py | deerflow/components/deeptutor_mcp.py | DeepTutor MCP Server |
| DeepCode framework | ~/DeepCode/agent/framework.py | 独立 DeepCode Agent |
| DeerFlow config | ~/.DeerFlow/config.yaml | DeerFlow MiniMax 配置 |
| DeepCode config | ~/DeepCode/config.py | DeepCode MiniMax 配置 |

## 排查入口

- **MCP server crash** → 使用 `mcp-debugging` skill
- **DeerFlow MCP 集成细节** → 使用 `deerflow-mcp-integration` skill
- **确认某个 MCP endpoint** → 本 skill Step 1 的健康检查
- **API key 配置错误** → 本 skill Step 2 检查各 config 文件
