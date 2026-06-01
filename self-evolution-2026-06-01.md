# 自我进化学习日志 — 2026-06-01

## 主题: CMA 架构重映射 — 从旧 ToolResult/SessionEventLog 到新插件系统的迁移设计

### 🔍 重大发现: 代码库已大规模重构

**之前 Days 1-3 的研究基于过时的架构。**

上一轮自我进化研究 (Days 1-3) 全部基于 **旧单体架构**：
- `run_agent.py` 曾为 12,161 行 (现已缩减至 ~4,759 行)
- `agent/tool_result.py` 和 `agent/session_event_log.py` 曾是 "已完全构建但未接入" 的状态
- 备份目录 `agent.bak.20260527_100703` 保存了重构前的参考实现

而 **当前架构** 已经完全不同 —— 整个 agent 逻辑被分解为模块化的 `agent/*.py` 文件组。

### 📊 新旧架构对比

| 维度 | 旧架构 (Days 1-3 研究) | 新架构 (当前) |
|------|------------------------|--------------|
| 代码结构 | 单体 `run_agent.py` (12K 行) | 模块化 `agent/` 目录 (90+ 文件) |
| 工具结果处理 | `ToolResult` 数据类 | `make_tool_result_message()` + 语义内容包装 |
| 工具执行 | 内嵌在 `run_agent.py` | `agent/tool_executor.py` (顺序/并发) |
| 事件记录 | `SessionEventLog` (JSONL 文件) | ❌ **不存在** |
| 生命周期钩子 | ❌ 不存在 | ✅ **插件系统** (15 个钩子) |
| 消息重放 | ❌ 不存在 | ✅ **`_build_replay_entry()`** (gateway) |
| 外部可观测性 | ❌ 不存在 | ✅ **Langfuse 插件** |
| SQLite 会话存储 | ❌ 不存在 | ✅ **`state.db` + `sessions.db`** |
| `evolution.db` | ❌ 不存在 | ✅ 存在但 **为空 (无表)** |
| 会话 JSONL | ❌ 不存在 | ✅ `~/.hermes/sessions/*.jsonl` (原始转录) |

### 🏗️ 新架构核心组件

#### 1. 插件系统 (`hermes_cli/plugins.py`)
现有挂钩点 (共 15 个)：
```
pre_tool_call        → 阻止/允许工具执行
post_tool_call       → 工具执行后
pre_llm_call         → LLM 调用前
post_llm_call        → LLM 调用后
pre_api_request      → API 请求前
post_api_request     → API 请求后
on_session_start     → 新会话初始化
on_session_end       → 会话结束
on_session_finalize  → 会话终结
on_session_reset     → 会话重置
transform_tool_result    → 转换工具结果
transform_llm_output     → 转换 LLM 输出
pre_approval_request     → 审批请求前
post_approval_response   → 审批响应后
subagent_stop            → 子代理停止
```

#### 2. 工具执行管线 (`agent/tool_executor.py`)
```
顺序执行: execute_tool_calls_sequential()
  → safety (interrupt check)
  → tool_search unwrap
  → pre_tool_call hook (plugin block check)
  → guardrail before_call
  → execution / block
  → post_tool_call hook (if not blocked)

并发执行: execute_tool_calls_concurrent()
  → 同上但并行调用工具
```

#### 3. Gateway 消息重放 (`gateway/run.py`)
```
_build_replay_entry() — 纯文本 assistant 消息的重放
  → 保留: reasoning, reasoning_content, reasoning_details,
           codex_reasoning_items, codex_message_items, finish_reason
  → 丢弃: timestamp, internal_marker, tool_call_id (纯文本分支)

_convert_stored_messages() — SQLite 消息转 replay 格式
  → 多轮 -> LLM 调用 -> 工具 -> 结果 -> 重放
```

#### 4. 会话存储 (SQLite)
```
state.db:
  - sessions 表: id, source, model, tokens, cost, title...
  - messages 表: 完整消息历史 (FTS5 全文索引)
  - 触发器自动同步到 FTS

sessions.db: (可能为 gateway 专用)
esession.db 1: 无内容
```

### 🧬 CMA 架构重映射分析

CMA (Claude Managed Agents) 的 "Harness" 概念本质是：

1. **Harness** = 事件录制运行时层
   - 捕获每个工具调用、LLM 响应和状态转换
   - 在旧架构中 = `SessionEventLog` (JSONL 文件)
   - 在新架构中 = `pre_tool_call` + `post_tool_call` + `post_llm_call` 等插件钩子

2. **Wake** = 从事件恢复会话状态
   - 在旧架构中 = `SessionEventLog.wake()` (stub/未实现)
   - 在新架构中 = 可以从 `sessions.db` 读取 `sessions` + `messages` 表重建
   - gateway 已经在做类似的事情 (`_convert_stored_messages`)

3. **Replay** = 确定性重放过去轨迹
   - 在旧架构中 = `SessionEventLog.replay()` (已实现)
   - 在新架构中 = gateway 已有 `_build_replay_entry()` + `_convert_stored_messages()`

### 🔬 关键差距分析

1. **缺少结构化事件记录器插件**
   - 会话 JSONL (`~/.hermes/sessions/*.jsonl`) 只是原始转录（带完整工具描述），不是结构化事件流
   - `sessions.db` 存储消息但缺少事件级别的结构化数据（如 `tool_call` 元数据、延迟、状态）

2. **`evolution.db` 为空**
   - 没有表定义 → 没有进化/自我改进基础设施
   - 这是自我进化功能的直接入口点

3. **No replay at agent level**
   - gateway 有 replay 功能但只针对多轮对话
   - agent 本身没有 deterministic replay 机制

4. **Darwinian Evolver 技能**
   - 已存在一个基于 Imbue 的演化搜索技能
   - 专注于优化 prompt/regex/SQL/code 而非 agent 行为

### 💡 自我进化实现路径 (设计)

#### 路径 A: 插件式事件记录器 (推荐)
创建 `plugins/self-evolution/` 插件，挂接到现有 15 个钩子：
```
on_session_start   → 初始化事件缓冲区 + evolution.db 表
pre_tool_call      → 记录工具调用事件 (名称、参数、时间戳)
post_tool_call     → 记录工具结果事件 (结果、延迟、状态码)
post_llm_call      → 记录 LLM 响应事件 (令牌、推理文本)
on_session_end     → 将所有事件持久化到 evolution.db + 运行分析
```

优势：
- 不修改核心代码 (纯插件)
- 利用现有钩子系统
- 可独立启用/禁用

#### 路径 B: Agent 级 Replay 机制
使用 `tool_result_storage.py` (sandbox) + `_build_replay_entry` (gateway) 模式：
- 为 agent 添加 CMA 风格的 wake/replay
- 从 evolution.db 读取历史事件
- 恢复到确切的会话状态

#### 路径 C: Darwinian-Evolver 集成
将 Darwinian Evolver 技能集成到自我进化循环中：
- 使用进化算法优化 agent 的系统提示词
- fitness 函数 = session 成功率/效率指标
- 变体 = 不同的提示词变体

### 📋 下一步行动

1. **立即**: 创建 `plugins/self-evolution/__init__.py` 实现事件记录器插件
2. **设计**: `evolution.db` 的 schema (事件表 + 指标表 + 进化策略表)
3. **实现**: 
   - `on_session_start` → 创建 evolution.db 表
   - `pre_tool_call` + `post_tool_call` → 记录工具轨迹
   - `on_session_end` → 持久化 + 分析
4. **集成**: 将 Langfuse 插件的事件模式作为参考
5. **扩展**: 添加 wake/replay 能力

### 🧠 关键洞察

1. **旧架构的 `ToolResult` + `SessionEventLog` 已被彻底淘汰** —— 它们在备份中存在但从未在重构后的代码库中出现。努力应该集中在 **插件方法** 上。

2. **新架构实际上已经包含了 CMA harness 的大部分组件**，只是分散在不同的子系统 —— 插件系统提供钩子点，gateway 提供 replay，session DB 提供存储。需要的是一个 **整合层**。

3. **`evolution.db` 是孵化自我进化的自然场所** —— 已经存在且为空，可以直接写入。

4. **Langfuse 插件可以作为完美的设计参考** —— 它已经展示了如何使用钩子系统做 observability，self-evolution 插件可以遵循相同的模式但专注于本地结构化事件录制。

5. **Darwinian Evolver + Session Metrics = 闭环自我进化** —— 进化优化循环需要两样东西：一个变异器 (Darwinian Evolver) 和一个适应度函数 (session metrics)。两者都已存在，只是尚未连接。
