# 学习笔记 — 2026-05-29 04:00（北京时间）

## 学习主题
**Hermes Agent 自我进化架构深度分析** — 梳理三大核心机制：委托/子代理、轨迹日志、基因响应系统

---

## 一、委托/子代理机制：`delegate_task`

### 架构定位
`delegate_task` 是 Hermes 的原生子代理工具，定义在 `hermes-agent/tools/tirith_security.py`，通过 `hermes-agent/tools/process_registry.py` 注册。与外部 CMA 的委托模型不同，Hermes 的委托是**同进程内工具调用**，而非跨进程/跨服务。

### 关键代码路径
```
hermes-agent/tools/tirith_security.py   ← delegate_task 定义
hermes-agent/tools/process_registry.py ← 工具注册中心
```

### 委托模型特点
- **工具化设计**：`delegate_task` 是普通工具，不是特殊构造
- **子代理有独立会话**：每个子代理获取独立 conversation、terminal session
- **不支持嵌套委托**：`max_spawn_depth=1`，叶子 subagent 无法再 spawn
- **两种角色**：`leaf`（默认，专注工作）和 `orchestrator`（可spawn，但被强制降级为leaf）
- **结果验证**：`delegate_task` 返回 summary 而非原始结果，需自行验证

### 与 CMA 委托对比
| 维度 | Hermes delegate_task | CMA Managed Agents |
|------|---------------------|-------------------|
| 传输方式 | 同进程工具调用 | 独立进程/服务 |
| 上下文 | 无当前会话记忆 | 有独立 memory |
| 嵌套 | max_depth=1，无嵌套 | 支持嵌套树 |
| 生命周期 | 随父会话结束 | 可独立长驻 |
| 工具化 | 纯工具 | Agent 抽象 |

---

## 二、轨迹/会话日志机制

### 三层存储架构

#### Layer 1: Honcho 原生会话（`~/.openclaw/agents/hermes-agent/sessions/`）
- 格式：JSONL，每行一个会话事件
- 内容：完整消息历史 + 工具调用 + 参数 + 结果
- 规模：~1524 个会话文件（持续增长）
- 用途：原始轨迹存储，Evolver 的数据源

#### Layer 2: Hermes SessionDB（`hermes_state.py`）
- SQLite + FTS5 全文搜索
- 表结构：`sessions`（元数据）+ `messages`（消息内容）
- 索引：`session_id` + `created_at`
- 用途：快速查询、搜索历史会话

#### Layer 3: Evolver 指标格式（`rtk_metrics.jsonl`）
- `hermes_to_evolver_bridge.py` 将 SessionDB 数据转换为 RTK 格式
- 每行：`{"session_id", "messages", "tool_calls", "turns", "tokens", "errors", ...}`
- 由 `evolver_analysis.py` 消费，生成 EvolutionEvent

### Trajectory Compressor
`hermes-agent/trajectory_compressor.py`（65KB）：处理轨迹压缩，用于减少上下文长度同时保留关键信息。

---

## 三、基因响应系统（Gene-Based Reactivity）

### 架构
`simplemem_evolution/gene_store.py` + `genes.json`：基于触发器-动作规则的响应系统，类似于反射机制。

### 核心组件
```python
gene = {
    "gene_id": str,
    "name": str,
    "triggers": [...],    # 触发条件
    "actions": [...],     # 响应动作
    "enabled": bool
}
```

### 管理接口
- `gene_add`: 注册新基因
- `gene_delete`: 删除基因
- `gene_match`: 检查上下文是否匹配任何基因
- `gene_record`: 记录基因执行结果（成功/失败）
- `gene_list`: 列出所有基因

### 演进事件（EvolutionEvent）存储
- **数据库**：`simplemem_evolution/evolution.db`（383条记录）
- **格式**：每条记录包含 `entry_id`、`content`、`weight`、`access_count`、`decay_history`
- **数据源**：`hermes-agent-self-evolution/assets/gep/events.jsonl`
- **同步桥**：`evolver_to_simplemem.py`（幂等、增量 checkpoint）

---

## 四、Evolver 管道（三阶段）

### Stage 1: hermes_to_evolver_bridge.py
```
SessionDB (SQLite) → rtk_metrics.jsonl
```
- 读取 honcho 会话文件
- 转换为 RTK 指标格式
- 按时间分批处理
- **状态**：May 28 后无新会话（Found 0 sessions to process）

### Stage 2: evolver_analysis.py
```
rtk_metrics.jsonl → signals.json + events.jsonl
```
- 分析 RTK 指标，检测信号：`low_engagement`, `context_bloat`, `skill_drift`
- 生成 EvolutionEvent
- **状态**：最后运行 May 26

### Stage 3: evolver_to_simplemem.py
```
events.jsonl → evolution.db (SimpleMem Evolution Store)
```
- 增量同步（53个已处理，跳过）
- 幂等写入（INSERT OR REPLACE）
- **状态**：May 28 后无新事件

---

## 五、Working Memory（7槽缓存）

当前活跃条目：
```
session-20260528_105201_|Feishu会话...
20260528_105201_-tool-delegate_task
20260528_105201_-tool-terminal
20260528_105201_-tool-cronjob
20260528_104523_-user-start（whisper进化失败诊断）
session-20260528_104523_|Feishu会话...
20260528_102605_-response
```
用户身份：`天融信安服团队经理 r00tcc`

---

## 六、关键发现

### 1. Evolver 管道已停顿
- `hermes_to_evolver_bridge.py`：最后处理会话 May 28，之后 0 sessions
- `evolver_analysis.py`：最后运行 May 26
- `evolver_to_simplemem.py`：最后运行 May 28
- **原因**：events.jsonl 文件不存在（路径问题：`/hermes-agent/hermes-agent-self-evolution/` vs `/hermes-agent-self-evolution/`）

### 2. 路径不一致问题
```
HERMES_DIR/hermes-agent/hermes-agent-self-evolution/  ← evolver_to_simplemem.py 使用的路径
HERMES_DIR/hermes-agent-self-evolution/               ← 实际目录位置
```
缺少一层 `hermes-agent/` 嵌套。

### 3. Skill Stats 为空
`skills/skill_stats.json` 存在但 `tier_counts` 和 `by_category` 为空对象 — skill quality tracking 系统尚未激活。

### 4. delegate_task 安全性
通过 `tirith_security.py` 处理，包含安全扫描逻辑（检测 pipe_to_interpreter 等危险模式）。

---

## 下一步行动

### 立即修复
1. **修复 evolver 路径问题**：更新 `EVOLVER_DIR` 路径或创建符号链接
2. **重新运行 bridge step 1**：处理积累的 honcho 会话文件
3. **激活 skill quality tracking**：运行 skill quality MCP 检查

### 深度研究
4. **分析 delegate_task 实现**：深入 `tirith_security.py` 的委托逻辑
5. **研究 trajectory_compressor.py**：理解 Hermes 的轨迹压缩策略
6. **对比 CMA 委托模型**：理解两种架构的权衡

### 架构改进提案
7. 设计跨会话基因学习机制（目前基因需手动注册）
8. 实现会话质量评分自动化（目前 evolver_analysis.py 依赖手动触发）
9. 建立 skill quality → evolution event 的自动反馈闭环