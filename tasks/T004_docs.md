# Hermes Agent 使用文档

## 什么是 Hermes Agent

**Hermes Agent** 是由 Nous Research 开发的一款开源、智能的 AI 编程与自动化助手。它运行在终端中，能够通过自然语言理解用户的意图，并自主调用各种工具来完成复杂任务——包括执行终端命令、读写文件、搜索代码、浏览网页、管理后台进程、编写代码等。

Hermes Agent 的核心理念是 **Agentic Coding**：让 AI 像一位熟练的开发者一样，主动分析问题、规划步骤、执行操作，并最终给出结果。它支持多轮对话、任务委派、上下文压缩、技能插件系统，以及通过 Gateway 接入 Telegram、Discord、Slack 等消息平台。

> **一句话总结**：Hermes Agent 是一个终端原生的 AI 编程助手，能够自主学习、规划和执行任务。

---

## 主要功能

### 1. `delegate_task` — 任务委派

将子任务派发给独立的 sub-agent 并行执行。支持两种模式：

- **单一任务**：设定一个 `goal`，sub-agent 独立完成。
- **批量任务**：通过 `tasks` 列表同时派发多个子任务，自动收集结果。

Sub-agent 有 `leaf`（不可再委派）和 `orchestrator`（可继续委派）两种角色。

### 2. `terminal` — 终端执行

在本地或容器中执行 Shell 命令。支持：

- **前台执行**：命令执行后立即返回结果，适合快速命令。
- **后台执行**：使用 `background=true` 启动长时间运行的任务（如服务器、构建），可通过 `process` 工具管理生命周期。
- **PTY 模式**：支持交互式 CLI 工具（如 Python REPL）。
- **多后端**：支持 `local`、`docker`、`ssh`、`modal`、`daytona`、`singularity` 等多种执行环境。

### 3. 文件操作

提供完整的文件读写能力：

- **`read_file`** — 读取文件内容，支持分页、偏移量控制。
- **`write_file`** — 写入/覆盖文件，自动创建父目录。
- **`patch`** — 基于模糊匹配的精确查找替换，支持 replace 和 patch 两种模式。
- **`search_files`** — 基于 ripgrep 的内容搜索和文件查找，支持正则和 glob 模式。

### 4. `web` — 网络检索与提取

- **`web_search`**：通过搜索引擎获取最新信息。
- **`web_extract`**：提取指定网页的结构化内容。

### 5. `browser` — 浏览器自动化

基于 Browserbase 的浏览器自动化能力，支持页面导航、点击、表单填写、截图等操作。

### 6. 技能与插件系统

- **Skills**：可安装的能力模块（存放在 `~/.hermes/skills/`），通过 `/skill` 命令调用。支持搜索、浏览和安装官方技能。
- **Plugins**：自定义插件系统，支持注册新工具、钩子和 CLI 子命令。
- **MCP 服务器**：通过 MCP 协议集成外部工具（如搜索、记忆、数据库等）。

### 7. 消息平台接入

通过 Gateway 支持多平台接入：

| 平台 | 工具集 |
|------|--------|
| Telegram | `hermes-telegram` |
| Discord | `hermes-discord` |
| Slack | `hermes-slack` |
| WhatsApp | `hermes-whatsapp` |
| Signal | `hermes-signal` |
| Home Assistant | `hermes-homeassistant` |
| QQ Bot | `hermes-qqbot` |

### 8. 其他重要功能

- **`cronjob`** — 定时任务调度，支持 Cron 表达式、间隔时间、ISO 时间戳等格式。
- **`code_execution`** — 安全的沙箱化代码执行。
- **`memory`** — 长期记忆与用户画像管理。
- **`vision`** — 图像分析与理解。
- **`image_gen`** — AI 图像生成。
- **`session_search`** — 历史会话全文检索（基于 FTS5）。
- **上下文压缩** — 自动压缩过长对话，节省 API 开销。
- **人物设定** — 内置多种人格（猫娘、海盗、莎士比亚、技术专家等），通过 `/personality` 切换。

---

## 使用示例

### 示例 1：启动 Hermes Agent CLI

```bash
# 启动交互式 CLI 会话
hermes

# 或使用 TUI（终端 UI）模式
hermes --tui
```

### 示例 2：让 Agent 完成一个数据分析任务

```
你 > 请帮我创建一个 Python 脚本，计算斐波那契数列的前 20 项，并保存到 fib20.txt 中。
```

Agent 会自动：
1. 使用 `write_file` 创建 Python 脚本
2. 使用 `terminal` 执行脚本
3. 使用 `read_file` 验证结果

### 示例 3：使用后台进程运行 Web 服务

```
你 > 帮我用 Python 启动一个简单的 HTTP 服务器在端口 8080，并在后台运行
```

### 示例 4：委派子任务

```
你 > 请同时帮我完成以下三件事：
1. 检查当前目录下的 Python 文件
2. 搜索 README.md 的内容
3. 查看系统磁盘使用情况
```

Agent 会自动利用 `delegate_task` 并行处理这些请求。

### 示例 5：在消息平台上使用

在 Telegram 中向 Hermes Agent 发送：

```
帮我总结最近一周的 Git 提交记录
```

### 示例 6：设置定时任务

```
你 > 请每天早上 9 点帮我检查系统更新
```

### 示例 7：安装并使用技能

```bash
# 安装官方技能
hermes skills install official/analysis/code-review

# 列出已安装技能
hermes skills list

# 在对话中使用技能
/skill code-review
```

---

## 配置与安装

### 配置文件

- **主配置**：`~/.hermes/config.yaml`
- **环境变量**：`~/.hermes/.env`（仅存放 API Key）
- **日志目录**：`~/.hermes/logs/`

### 快速安装

```bash
# 克隆仓库
git clone https://github.com/nousresearch/hermes-agent.git
cd hermes-agent

# 安装依赖
pip install -e .

# 初始化配置
hermes setup

# 启动
hermes
```

### 主要配置项

```yaml
model:
  default: anthropic/claude-opus-4.6  # 默认模型
  provider: openrouter                 # 模型提供商

terminal:
  backend: local                       # 终端后端（local/docker/ssh）
  timeout: 180                         # 命令超时（秒）

agent:
  max_turns: 90                        # 最大对话轮次
```

---

## 更多资源

- **官方文档**：<https://hermes-agent.nousresearch.com/docs>
- **GitHub 仓库**：<https://github.com/nousresearch/hermes-agent>
- **技能市场**：通过 `hermes skills` 命令浏览和安装
