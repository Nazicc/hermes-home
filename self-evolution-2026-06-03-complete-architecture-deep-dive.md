# 2026-06-03 自我进化：完整架构深潜与插件桥接设计

## 摘要
▸ 完整架构映射 3 层 ✅
▸ 现状核心鸿沟确认 ✅
▸ 插件桥接设计（evolution-recorder） ✅
▸ 下一步实现路径 ✅

---

## 背景：11 天研究进展

| 日期 | 阶段 | 核心发现 |
|------|------|----------|
| 5/19-20 | Day 1: ToolResult 标准化 | ToolResult 类存在但未集成进 pipeline |
| 5/21 | Day 2: Session Event Log | SessionEventLog 类存在，7种事件类型 |
| 5/22 | Day 3: 尝试压缩/wake() | 遇到代码库结构问题 |
| 5/24 | Day 4: Harness Plugin | hooks 系统发现 |
| 5/25 | 自由探索 | 深入 pipeline 架构 |
| 5/26 | Day 3 重做 + 状态审计 | 发现 skill 数据过期 |
| 5/27 | CMA 集成审计 | 5 元组模式确认 |
| 5/28 | 自我进化 Pipeline 深潜 | 11个已进化 skill、GEPA/MIPROv2 分析 |
| 5/30 | Pipeline 分析 | MIPROv2 回退问题 |
| 6/1 | CMA 架构重映射 | **惊天发现：代码库已重构！** |
| 6/3 | **今日：完整桥接设计** | 鸿沟分析 + 实现方案 |

---

## Layer 1: Evolution Pipeline (`hermes-agent-self-evolution/`)

```
hermes-agent-self-evolution/
├── evolution/
│   ├── skills/
│   │   ├── evolve_skill.py      # 主入口：加载→数据集→优化→验证→部署
│   │   └── skill_module.py      # DSPy skill module 定义
│   ├── core/
│   │   ├── config.py            # EvolutionConfig
│   │   ├── dataset_builder.py   # 合成/金标/会话DB 三种数据源
│   │   ├── constraints.py       # 约束检查
│   │   ├── external_importers.py # 外部导入
│   │   └── fitness.py           # 适应度评估
│   ├── code/                    # 代码进化
│   ├── monitor/                 # 监控
│   ├── prompts/                 # 提示模板
│   └── tools/                   # 工具支持
├── run-evolution.sh             # cron 入口
└── datasets/                    # skill 数据集
```

### 核心数据流

```
run-evolution.sh
  → evolution/skills/evolve_skill.py
    → build_dataset(): [synthetic | golden | sessiondb]
    → DSPy.optimize(): GEPA → MIPROv2 (fallback)
    → validate_skill()
    → deploy_skill() → ~/.hermes/skills/<name>.md
```

### 数据集结构

```python
@dataclass
class EvalExample:
    task_input: str       # 用户提问
    expected_behavior:str # 评分标准
    difficulty: str       # easy/medium/hard
    category: str         # 测试类别
    source: str           # synthetic/sessiondb/golden
```

- 合成数据：LLM 读 skill → 自动生成
- 金标数据：手工 JSONL
- **SessionDB mining**: 完全未使用！(源码中定义了 source='sessiondb' 但无实现)

---

## Layer 2: Memory/Storage (`simplemem_evolution/`)

### 数据库
```sql
evolution_entries (
    entry_id TEXT PRIMARY KEY,
    weight REAL,
    access_count INTEGER,
    last_accessed TEXT,
    created_at TEXT,
    decay_history TEXT,
    content TEXT
)
```
- **530 条记录** | 最高 weight: 1.0 | 内容为工具执行记录
- 遗忘系统：访问衰减 + 阈值删除
- 工作记忆：7 槽重要性缓存

### MCP Server (FastMCP)
```python
tools:
  - evolution_remember(content, weight, tags, source)
  - evolution_delete(entry_id)
  - evolution_decay()
  - working_memory_add(entry_id, summary, importance)
  - working_memory_list()
  - gene_add(gene_id, triggers, actions)
```

---

## Layer 3: Plugin System (`hermes_cli/plugins.py`)

### 15 个有效 Hook

| Hook | 触发时机 | 关键参数 |
|------|----------|----------|
| `pre_tool_call` | 工具执行前 | tool_name, args |
| **`post_tool_call`** | **工具执行后** | **tool_name, args, result, task_id, session_id, tool_call_id, duration_ms** |
| `transform_tool_result` | 结果返回前 | tool_name, args, result |
| `pre_llm_call` | LLM 调用前 | user_message, conversation_history |
| `post_llm_call` | LLM 调用后 | user_message, assistant_response |
| `pre_api_request` | API请求前 | request_messages, model, provider |
| `post_api_request` | API请求后 | response, usage, finish_reason |
| `on_session_start` | 会话开始 | session_id, model, platform |
| `on_session_end` | 会话结束 | session_id, completed, interrupted |
| `on_session_finalize` | 会话定稿 | session_id |
| `add_slash_commands` | 注册命令 | - |
| `on_shutdown` | 关闭 | - |
| `transform_terminal_output` | 终端输出 | - |
| `addon_activated` | 插件激活 | - |
| `addon_deactivated` | 插件停用 | - |

### 插件注册模式
```python
def register(ctx: PluginContext):
    ctx.register_hook("post_tool_call", handler)
    ctx.register_hook("on_session_end", handler)
    ctx.register_tool(name, handler, description, schema)
    ctx.register_slash_command(name, handler, description)
```

### 参考实现
- `hermes-agent/plugins/disk-cleanup/` — 最简单的完整插件
- `hermes-agent/plugins/observability/langfuse/` — 复杂监控插件
- `hermes-agent/plugins/.internal/` — 内部插件

---

## ⚠️ 核心鸿沟分析：三层为何互不连通

### 现状
```
                     +--------------------+
                     |   Evolution Pipeline  |  ← cron 运行，离线
                     |  (DSPy + GEPA)       |
                     +---------+-----------+
                               |
                     (纯合成数据,无反馈)
                               |
                     +---------v-----------+
   Runtime Execution  |  simplemem_evolution |  ← 530条历史记录
   (Plugin Hooks)     |  (MCP + 遗忘系统)    |     但已停止更新
                     +--------------------+
```

### 三个断裂

1. **Runtime → Evolution**: 无插件捕获实时执行数据给进化 pipeline
   - `post_tool_call` 未被用于进化数据采集
   - LLM 决策质量、工具失败率、耗时等指标未跟踪
   
2. **Evolution → Runtime**: 进化 pipeline 优化结果无运行时反馈
   - skill 更新后无自动 A/B 测试
   - 无法感知优化是否提升效果

3. **Storage 分裂**: 三种存储互不关联
   - `evolution.db` (root) — 空数据库，无表结构
   - `simplemem_evolution/evolution.db` — 530条历史，已停止更新
   - `.hermes_archive/evolution.db` — 旧存档

---

## 今日设计：Evolution-Recorder 插件桥接

### 第一个实现：Runtime 数据捕获层

```
post_tool_call hook
    → 捕获: tool_name, args, result (error/success/exit_code)
    → 提取: 成功/失败/耗时/资源消耗
    → 结构化为 EvalExample 格式
    → 写入 simplemem_evolution (MCP)

on_session_end hook
    → 汇总本轮所有工具调用
    → 计算成功率、平均耗时
    → 生成 session 摘要记录
    → 写入 evolution 存储
```

### 设计文档

```python
# ~/.hermes/plugins/evolution-recorder/plugin.yaml
name: evolution-recorder
version: 1.0.0
description: "Capture runtime tool execution data for self-evolution pipeline"
hooks:
  - post_tool_call
  - on_session_end
  - on_session_start
tools:
  - evolution_status: "Show current evolution recording stats"
```

```python
# ~/.hermes/plugins/evolution-recorder/__init__.py
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

@dataclass
class ToolExecutionRecord:
    tool_name: str
    args: dict
    result_success: bool
    error_message: Optional[str] = None
    duration_ms: int = 0
    timestamp: str = ""
    task_id: str = ""
    session_id: str = ""
    tool_call_id: str = ""

@dataclass
class SessionSummary:
    session_id: str
    started_at: str
    tool_count: int
    success_count: int
    failure_count: int
    avg_duration_ms: float
    total_duration_ms: float
    completed: bool
    interrupted: bool

def _on_post_tool_call(
    tool_name: str = "",
    args: Optional[dict] = None,
    result: Any = None,
    task_id: str = "",
    session_id: str = "",
    tool_call_id: str = "",
    duration_ms: int = 0,
    **_,
) -> None:
    """Capture tool execution result."""
    # Analyze result for success/failure
    success, error = _analyze_result(tool_name, result)
    
    record = ToolExecutionRecord(
        tool_name=tool_name,
        args=dict(args) if args else {},
        result_success=success,
        error_message=error,
        duration_ms=duration_ms,
        timestamp=datetime.utcnow().isoformat(),
        task_id=task_id,
        session_id=session_id,
        tool_call_id=tool_call_id,
    )
    
    # Store via MCP or local SQLite
    _persist_tool_execution(record)

def _analyze_result(tool_name: str, result: Any) -> tuple[bool, Optional[str]]:
    """Determine if tool call succeeded."""
    if result is None:
        return False, "No result returned"
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if "error" in parsed:
                return False, parsed["error"]
        except json.JSONDecodeError:
            pass
    return True, None
```

### 连接 Evolution Pipeline

将 Evolution-Recorder 的数据送入 `simplemem_evolution` MCP：

```python
# 在 _persist_tool_execution 中
from mcp_simplemem_evolution import evolution_remember

evolution_remember(
    entry_id=f"tool_{tool_call_id}",
    content=json.dumps({
        "tool_name": record.tool_name,
        "success": record.result_success,
        "error": record.error_message,
        "duration_ms": record.duration_ms,
        "timestamp": record.timestamp,
        "task_input": record.args.get("command", "") 
                       or record.args.get("content", "")[:200],
    }),
    weight=1.0 if not record.result_success else 0.5,  # 失败事件权重更高
    tags=[record.tool_name, "runtime", "auto-capture"],
    source="evolution_recorder_plugin",
)
```

---

## 目前研究已完成的里程碑

▸ **Phase 1** (5/19-5/24): 旧架构彻底分析 ✅
▸ **Phase 2** (5/25-5/28): Self-Evolution Pipeline 完整映射 ✅
▸ **Phase 3** (6/1): 新架构（重构后）映射完成 ✅
▸ **Phase 4** (6/3): 三层架构鸿沟分析 + 桥接设计 ✅

### 接下来的实现优先级

1. **立即** — 创建 `evolution-recorder` 插件（捕获运行数据）
2. **24h** — 插件上线后 24 小时内积累真实训练数据
3. **48h** — 修改 `dataset_builder.py` 增加 sessiondb 实际挖掘实现
4. **72h** — 首次全自动进化循环：Runtime→Capture→Store→Optimize→Deploy→Verify

---

## 关键文件索引

| 文件 | 行数 | 内容 |
|------|------|------|
| `hermes-agent/hermes_cli/plugins.py` | ~1100 | 插件系统核心：15 hooks, PluginContext, invoke_hook |
| `hermes-agent/hermes_cli/hooks.py` | ~240 | Hook 定义与钩子配置 |
| `hermes-agent/agent/conversation_loop.py` | ~4707 | 主循环，invoke_hook 调用点 |
| `hermes-agent/agent/tool_executor.py` | ~400 | 工具执行器 |
| `hermes-agent/model_tools.py` | ~1067 | post_tool_call 调用点 (line 996) |
| `hermes-agent-self-evolution/evolution/skills/evolve_skill.py` | ~400 | DSPy 进化主入口 |
| `hermes-agent-self-evolution/evolution/core/dataset_builder.py` | 232 | 数据集构造器 |
| `simplemem_evolution/simplemem_evolution_mcp.py` | ~400 | MCP 存储服务 |
| `hermes-agent/plugins/disk-cleanup/__init__.py` | 316 | 参考插件实现 |
| `hermes-agent/plugins/disk-cleanup/plugin.yaml` | ~15 | 插件清单 |
| `hermes-agent-self-evolution/run-evolution.sh` | ~60 | Evolution cron 入口 |
