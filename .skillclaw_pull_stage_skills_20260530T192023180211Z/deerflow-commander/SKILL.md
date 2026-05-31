---
name: deerflow-commander
description: "Use when needing deep research, multi-step web analysis, literature review, or report generation via DeerFlow MCP. DeerFlow acts as the execution layer while hermes-agent orchestrates. NOT for: simple single-step tasks, quick factual lookups, real-time interactive creative tasks, or when the shared MiniMax M2.7 model is overloaded."
category: general
---

## Architecture


hermes-agent (编排层)
  ↓ MCP
DeerFlow MCP Server → DeerFlowClient
  ↓
Ollama / OpenAI / MiniMax 等 LLM
  ↓
内置 Skills + Web 工具 (DuckDuckGo, Jina AI, Bash)


- **hermes-agent**：编排层（你）
- **DeerFlow**：执行层（子 agent、memory、sandboxes），位于 `/Users/can/.hermes/deer-flow-repo/`
- 共享 MiniMax M2.7 模型（via Token Plan `sk-cp-...`）
- 状态：健康（`deerflow_health` 返回 `healthy`）

**配置路径**：`/Users/can/.hermes/deer-flow-repo/config.yaml`
**日志路径**：`~/.hermes/deer-flow-repo/logs/`

## 何时委托

**委托给 DeerFlow**：
- 多源 web 研究与综合（5+ 网页）
- 文献综述（ArXiv、学术论文分析）— DeerFlow 有内置技能
- 竞品分析 + 数据收集
- 深度调查报告生成
- 多步骤研究工作流
- 需要 DeerFlow 子 agent 编排的任务

**不委托给 DeerFlow**：
- 简单的事实问答（直接回答更快）
- 只需单步工具的任务（terminal、jupyter、git 等 hermes-agent 自有工具即可）
- 需要实时交互的创意任务
- 非常简短的响应（1-3 句话）
- 简单文件操作（terminal 可处理）
- DeerFlow 共享模型（MiniMax M2.7）满载时

## MCP 工具

| 工具 | 用途 | 超时 |
|------|------|------|
| `deerflow_chat(message, thread_id?, thinking_enabled?, model_name?)` | 主工具，发送同步任务 | ~60s |
| `deerflow_stream(message, thread_id?, thinking_enabled?)` | 流式版本，适合长任务 | 无限制 |
| `deerflow_list_skills(enabled_only?)` | 列出所有技能（21个内置） | — |
| `deerflow_health()` | 健康检查 | — |

**参数说明**：
- `thread_id`：对话线程 ID，不提供则创建新线程
- `thinking_enabled`：默认 true，启用链式思维推理
- `model_name`：可选，默认使用 Token Plan 配置的 MiniMax M2.7

## 超时约束与应对

`deerflow_chat` 有 ~60s MCP 超时限制。复杂推理任务（thinking_enabled=true）很容易超时。

**应对策略（按优先级）**：
1. **禁用 thinking**：`thinking_enabled: false` — 不需要展示推理过程时用，减少延迟
2. **简化 prompt** — 把多步任务拆成串行简单调用
3. **使用 stream 模式**：`deerflow_stream` — 长任务用 stream 避免超时
4. **设置预期** — 深度研究报告预期 5-10 分钟，提前告知用户等待

## 委托策略

| 任务类型 | 推荐方式 | 超时预期 |
|----------|----------|----------|
| 简单问答（1-3句话） | `deerflow_chat` + `thinking_enabled: false` | < 30s |
| 单次搜索+综合 | `deerflow_chat` + `thinking_enabled: false` | 30-120s |
| 多步骤研究/报告生成 | `deerflow_stream` | 2-10min |
| 文献综述/竞品分析 | `deerflow_stream` + `thread_id` | 5min+ |

## 实际操作流程

1. **评估任务复杂度**
   - 简单问答 → 直接 `deerflow_chat`
   - 多步骤 research、报告生成 → `deerflow_stream`

2. **构造请求**
   - 用中文写清晰的研究目标
   - 指定输出格式（如：结构化报告、表格、markdown）
   - 复杂任务开启 `thinking_enabled: true`

3. **处理结果**
   - 同步调用：直接解析返回的 messages
   - 流式调用：收集流式输出，整合成最终报告

4. **错误处理**
   - `TimeoutError`：任务超时，切换 `deerflow_stream` 重试，或告知用户任务太复杂
   - `not_found`：DeerFlow MCP 工具未注册，检查 MCP 配置
   - 其他错误：查看 DeerFlow 日志 `~/.hermes/deer-flow-repo/logs/`

## 常用技能参考

用 `deerflow_list_skills(enabled_only=false)` 查询全部。

| 技能名 | 用途 |
|--------|------|
| `academic-paper-review` | 论文复现、批判性分析 |
| `arxiv` | ArXiv 论文搜索与阅读 |
| `github` / `github-repo-analysis` | GitHub 代码/仓库分析 |
| `code-execution` | 代码编写与调试 |
| `web-search` / `web-search-report` | DuckDuckGo 搜索 |
| `image_search` | 图片搜索 |
| `visualization` | 图表生成 |
| `file-search` | 文件内容搜索与分析 |

## 消息撰写要点

- 明确说明**任务目标**和**输出格式**（如"输出一份包含引用的结构化报告"）
- 指定**搜索范围**和**时间范围**（如"2024-2025年"）
- 对于多步骤任务，在一条消息里描述完整流程比拆分成多个调用更高效
- 提供**背景信息**（如相关公司/技术/领域上下文）
- 包含 thread_id 以保持多轮对话的上下文连贯性
- 如需特定技能，明确提及技能名称

## 示例

**深度研究（推荐用 stream）**：
python
mcp_deerflow_deerflow_stream({
    "message": "研究 2024-2025年 AI Agent 领域的最新进展，重点关注架构创新和实际落地案例。输出结构化报告，包含：1) 技术架构演进 2) 主流框架对比 3) 落地案例 4) 未来趋势。请搜索至少5个信息源。",
    "thinking_enabled": true
})


**论文综述**：
python
mcp_deerflow_deerflow_chat({
    "message": "用 arxiv 技能搜索近半年关于 LLM reasoning 的论文，筛选高引用量（>50）且与 agent 相关的论文，给出每篇的核心贡献和方法论分析，以表格形式输出。",
    "thread_id": "llm-agent-review-001",
    "thinking_enabled": true
})


**快速问答（禁用 thinking 避免超时）**：
python
mcp_deerflow_deerflow_chat({
    "message": "解释什么是 MCP (Model Context Protocol) 以及它与传统 API 集成的区别，用通俗语言解释。",
    "thinking_enabled": false
})


**GitHub 代码分析**：
python
mcp_deerflow_deerflow_chat({
    "message": "对 https://github.com/xxx/yyy 进行深度代码分析，输出结构化报告"
})


**列出可用技能**：
python
mcp_deerflow_deerflow_list_skills(enabled_only=false)

