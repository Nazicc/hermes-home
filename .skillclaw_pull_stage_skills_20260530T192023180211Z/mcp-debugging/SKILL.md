---
name: mcp-debugging
description: "调试 Hermes Gateway MCP 服务器崩溃的系统方法。Use when an MCP tool returns errors, a server process is missing, or MCP health checks fail. NOT for: network-level issues, LLM provider failures, or skill content bugs (those have their own skills)."
category: general
trigger: MCP tool returns errors, server process missing, or MCP health checks fail
...
not_for: network-level issues, LLM provider failures, skill content bugs
...
---

# MCP 服务器调试方法（Hermes Gateway）

## 核心原则

**Gateway 重启后，旧进程日志会残留！不要直接相信日志文件的最新内容。**

MCP 服务器作为 gateway 子进程运行，其错误日志可能来自**已经崩溃的旧 gateway 实例**，而非当前运行的进程。

**关键验证顺序**：
1. 先用 `ps aux | grep mcp` 确认当前是否有 MCP 进程
2. 再读错误日志——如果日志文件的时间戳早于当前 gateway 启动时间，则日志已过时
3. 用 MCP 工具本身做健康检查（如 `mcp_deerflow_deerflow_health`）

**调试顺序：** 1. 观察（Observe）→ 2. 假设（Hypothesize）→ 3. 测试（Test）→ 4. 迭代（Iterate）

> ⚠️ **重要：** 不理解问题根源之前，不要进行任何修改。不成熟的修复会制造技术债务。

## Phase 1: 观察（Observe）

首先确认问题范围：

bash
# 1. 检查 gateway 进程是否运行
gateway_pid=$(pgrep -f "hermes.*gateway" | head -1)
echo "Gateway PID: $gateway_pid"
if [ -z "$gateway_pid" ]; then
  echo "Gateway 未运行！先启动它。"
fi

# 2. 检查 MCP 子进程（严格匹配 gateway PID 的子进程）
pgrep -P $gateway_pid -a

# 3. 查看日志目录中的所有错误日志
ls -la ~/.hermes/logs/*.error.log 2>/dev/null

# 4. 检查日志文件的最后修改时间（判断是否来自旧的 gateway）
for f in ~/.hermes/logs/*.error.log; do
  echo "=== $f ==="
  stat -f "%Sm %z" "$f" 2>/dev/null || stat -c "%y" "$f" 2>/dev/null
done

# 5. 获取 gateway 进程的启动时间
gw_start=$(ps -p $gateway_pid -o lstart= 2>/dev/null)
echo "Gateway 启动时间: $gw_start"


**判断标准：** 如果错误日志的最后修改时间 **早于** gateway 进程的启动时间，说明这是旧的残留日志，不代表当前状态。

## Phase 2: 假设（Hypothesize）

根据观察结果形成假设：

| 假设 | 描述 |
|------|------|
| **A** | MCP 子进程全部缺失 — Gateway 可能未启动 MCP 服务器 |
| **B** | 部分 MCP 子进程缺失 — 某些 MCP 服务器启动失败，可能是配置或权限问题 |
| **C** | MCP 工具调用失败（通信问题）— MCP 服务器在运行但客户端请求失败 |
| **D** | 模块导入错误（ModuleNotFoundError）— Python 环境问题，缺少依赖包 |

## Phase 3: 测试（Test）

### 测试 A: 验证 gateway 配置

bash
# 查看 MCP 服务器配置
grep -A 20 "mcp_servers" ~/.hermes/config.yaml 2>/dev/null || \
grep -A 20 "mcp" ~/.hermes/config.yaml 2>/dev/null

# 检查配置中指定的 Python 解释器路径
grep "python" ~/.hermes/config.yaml | grep -v "^#"


### 测试 B: 验证 MCP 服务器进程

bash
gateway_pid=$(pgrep -f "hermes.*gateway" | head -1)
echo "Gateway PID: $gateway_pid"

# 详细列出 MCP 子进程
for child in $(pgrep -P $gateway_pid 2>/dev/null); do
  echo "--- 子进程 PID $child ---"
  ps -p $child -o comm=,args= 2>/dev/null
  # 检查该进程使用的 Python 环境
  lsof -p $child 2>/dev/null | grep "\.venv\|site-packages" | head -3
done


### 测试 C: 验证 Python 模块导入

bash
# 根据 config.yaml 中的 python 路径测试导入
~/.hermes/hermes-agent/venv/bin/python -c "import langchain; print('langchain OK')" 2>&1
~/.hermes/deer-flow-repo/backend/.venv/bin/python -c "import langchain; print('langchain OK')" 2>&1
~/.hermes/simplemem_evolution/.venv/bin/python -c "import simplemem; print('simplemem OK')" 2>&1


### 测试 D: 健康检查工具

直接调用 MCP 工具做健康检查（而非读日志）：
- `mcp_deerflow_deerflow_health` — DeerFlow 状态
- `mcp_simplemem_search_memories` — SimpleMem 连接
- `mcp_skills_quality_quality_list_skills` — Skills-Quality 状态
- `mcp_simplemem_evolution_evolution_stats` — SimpleMem Evolution 状态

如果工具返回正常结果，说明 MCP 服务器正在运行，问题已解决。不要再相信旧的错误日志。

## Phase 4: 迭代（Iterate）

根据测试结果决定下一步：

| 测试结果 | 行动 |
|----------|------|
| 所有 MCP 子进程都缺失 | Gateway 配置可能有问题，或 `--mcp` flag 未启用 |
| 模块导入失败 | pip install 缺失的包到对应的 Python 环境 |
| MCP 工具返回错误 | 检查 MCP 服务器端口是否在监听 |
| 进程存在但不健康 | 查看具体错误日志（确认时间戳是否当前） |

## 常见错误诊断

| 错误 | 原因 | 修复 |
|------|------|------|
| `No module named 'langchain'` | DeerFlow 使用了错误的 Python（系统 Python 而非 backend/.venv） | 检查 config.yaml 中 python 路径指向 backend/.venv，重启 Gateway |
| `No module named 'simplemem'` | 依赖未安装 | 对应 venv 中执行 `pip install simplemem` |
| `FileNotFoundError: config.yaml` | DeerFlow 配置文件缺失 | 检查 `~/.hermes/deer-flow-repo/config.yaml` |
| `Cannot send a request, as the client has been closed` | MCP client session 因 gateway 重启断开 | 等待 10 秒后重试 live 调用 |
| `Connection refused` | 服务端口未就绪 | 等待 5 秒后重试；检查进程是否存活 |
| `ClosedResourceError` | MCP 客户端 session 过期 | gateway 重启后需要重新连接，工具本身可能正常 |
| MCP 子进程全部消失 | Gateway 完全崩溃 | 重启 Gateway |
| 子进程存在但 MCP 超时 | MCP 服务器卡住 | Kill 子进程后重启 Gateway |
| MCP 进程无错误日志但工具调用失败 | MCP 进程已崩溃但未写日志 | 检查进程退出码 |
| 错误日志存在但进程健康 | 旧 gateway 的残留日志 | 验证日志时间戳，忽略过时日志 |

## 不要做的事

- **不要**仅凭错误日志判断 MCP 健康状态 — 必须验证日志时间戳
- **不要**在 gateway 重启后立即读旧日志 — 旧日志会残留
- **不要**猜测 Python 环境 — 用 `ps aux` 确认实际使用的解释器路径

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "错误日志说 langchain 缺失，说明包没装" | 包可能已装在正确的 venv 中，但 MCP 进程使用了错误的 Python。直接测试 venv 中的 import 比相信日志更可靠 |
| "错误日志有内容，说明服务器还在报错" | 如果日志修改时间早于 gateway 启动时间，日志是旧 gateway 残留的，不代表当前状态 |
| "MCP 工具返回 ClosedResourceError，说明服务器挂了" | 这是 session 绑定到旧 gateway 的问题，不影响服务器本身 |
| "重启 gateway 太麻烦，先看看日志能不能找到原因" | 日志可能来自旧 gateway，先确认日志时效性比盲目分析更高效 |
| "进程列表显示 MCP 在跑，说明一切正常" | MCP 进程可能在运行但 health 工具调用失败，需要实际测试 |

## MCP 服务器列表

| MCP | 进程名 | Python 环境 | 健康检查工具 |
|-----|--------|------------|-------------|
| sirchmunk | `sirchmunk mcp serve` | openharness-venv | `mcp_skills_quality_quality_list_skills` |
| simplemem | `simplemem_mcp.py` | openharness-venv | `mcp_simplemem_search_memories` |
| simplemem-evolution | `simplemem_evolution_mcp.py` | hermes-agent venv | `mcp_simplemem_evolution_evolution_stats` |
| skills-quality | `skills_quality_mcp.py` | hermes-agent venv | `mcp_skills_quality_quality_list_skills` |
| deerflow | `deerflow_mcp.py` | deer-flow-repo .venv | `mcp_deerflow_deerflow_health` |

## 已知环境细节

| MCP 服务器 | 依赖包 | 所需 Python 环境 |
|------------|--------|------------------|
| DeerFlow | `langchain`, `deerflow` | `~/.hermes/deer-flow-repo/backend/.venv` |
| SimpleMem | `simplemem` | `~/.openharness-venv` |
| Sirchmunk | 独立 | 独立 venv |
| Skills-quality | 独立 | `hermes-agent` venv |

## 快速诊断清单

bash
# 1. 当前 gateway PID
gw_pid=$(pgrep -f "hermes_cli.main gateway run") && echo "Gateway PID: $gw_pid"

# 2. Gateway 启动时间
gw_start=$(ps -p $gw_pid -o etime= 2>/dev/null) && echo "Gateway running: $gw_start"

# 3. MCP 进程状态
ps aux | grep -E "deerflow-mcp|simplemem|skills-quality" | grep -v grep

# 4. 错误日志新鲜度（仅 mtime > gateway_start 时才读）
stat -f "%Sm %z" ~/.hermes/logs/*mcp*.log


- [ ] Gateway 进程是否运行？`ps aux | grep hermes.*gateway`
- [ ] Gateway 启动时间和错误日志修改时间哪个更早？
- [ ] 错误日志是当前 gateway 的还是旧 gateway 的？
- [ ] MCP 服务器进程是否在运行？`ps aux | grep mcp`
- [ ] 各 venv 中的依赖包是否可用？
- [ ] MCP 健康检查工具是否返回正常？

## Gateway 重启命令

### 重启特定 MCP（保留 Gateway）

Gateway 会自动 respawn 子进程：

bash
# 杀掉旧 MCP 进程
pkill -f "deerflow_mcp.py"
pkill -f "simplemem_evolution_mcp.py"

# 等待 gateway 重拉（10 秒）
sleep 10
ps aux | grep -E "deerflow|simplemem" | grep -v grep


### 完全重启 Gateway

bash
# 停止旧 gateway
pkill -f "hermes_cli.main gateway run" && sleep 2

# 启动新 gateway
cd ~/.hermes/hermes-agent && source venv/bin/activate
nohup hermes run gateway --replace > ~/.hermes/logs/gateway.log 2>&1 &

# 验证
sleep 10
ps aux | grep "hermes_cli.main gateway run" | grep -v grep
curl -s localhost:8000/health || echo "Gateway not responding"


### 手动启动单个 MCP（如果未自动重启）

bash
/Users/can/.hermes/deer-flow-repo/backend/.venv/bin/python /Users/can/.hermes/deerflow-mcp/deerflow_mcp.py &


## 常见问题快速修复

### Python 模块缺失

bash
# 找到正确的 pip 并安装
~/.hermes/hermes-agent/venv/bin/pip install <package>
~/.hermes/deer-flow-repo/backend/.venv/bin/pip install <package>


### 端口被占用

bash
# 找到占用端口的进程
lsof -i :<端口号>
# 或
netstat -an | grep <端口号>


### 重新安装 hermes-agent

bash
cd ~/.hermes/hermes-agent
git pull
pip install -e . --quiet


## 日志文件位置参考

| 日志文件 | 路径 |
|----------|------|
| Gateway 主日志 | `~/.hermes/logs/gateway.log` |
| 各 MCP 错误日志 | `~/.hermes/logs/<name>-mcp.error.log` |
| 配置参考 | `~/.hermes/config.yaml` — `mcp_servers` section |

## 相关技能

- `systematic-debugging` — 通用的 4 阶段调试方法（适用于非 MCP 问题）
- `pip-editable-debugging` — `pip install -e` 成功但 `import` 失败时的调试
