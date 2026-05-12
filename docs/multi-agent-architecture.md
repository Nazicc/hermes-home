# Hermes 多 Agent 团队架构设计

> 版本: v1.0 | 日期: 2026-05-12
> 原则: 纯 Hermes 原生，零 Claude Code 依赖

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Hermes Lead (你当前对话)                      │
│  角色: 调度中心 / 任务拆解 / 质量把关 / 用户交互                      │
│  工具: 全部 157 tools + 9 MCP + 106 skills                         │
│  能力: clarify(交互) / memory(持久) / cron(定时) / process(进程管理) │
└──────────┬──────────┬──────────┬──────────┬────────────────────────┘
           │          │          │          │
     ┌─────▼────┐ ┌──▼─────┐ ┌─▼──────┐ ┌─▼──────────┐
     │ Worker-A │ │Worker-B│ │Worker-C│ │  Cron-Patrol│
     │  持久进程 │ │ 持久进程│ │一次性  │ │   定时巡检   │
     └──────────┘ └────────┘ └────────┘ └─────────────┘
```

---

## 二、三层 Agent 原语（已验证可用）

| 层级 | 原语 | 持久性 | 工具集 | 通信 | 适用场景 |
|------|------|--------|--------|------|----------|
| L1 | `delegate_task` | 一次性 | 无MCP/无memory/无clarify | 仅返回summary | 快速子任务、并行搜索 |
| L2 | `process` + `hermes chat -q` | 持久进程 | 全部(157+9MCP) | process.write/poll + 邮箱 | 长任务、需工具调用 |
| L3 | `cronjob` | 周期性 | 全部(独立会话) | cron output → Lead | 定时巡检、数据同步 |

---

## 三、L2 Worker 详细架构（核心）

### 3.1 启动方式

```bash
# Lead 通过 terminal(background=true) 启动 Worker
terminal(command="hermes chat -q '你是 Worker-A，等待任务' -m glm-5.1 --worktree --pass-session-id",
         background=true,
         notify_on_complete=false)

# 返回 session_id，Lead 保存到 /tmp/team-{id}/registry.json
```

**已验证命令行参数：**
- `-q "prompt"` — 单次查询模式，执行后输出答案
- `-m glm-5.1` — 指定模型
- `--resume SESSION_ID` — 恢复上下文继续对话 ✅ 已验证
- `--worktree` — Git worktree 隔离（并行改代码不冲突）✅ 已确认
- `--pass-session-id` — 输出 session_id 用于后续恢复 ✅ 已验证

### 3.2 多轮通信协议

```
┌──────────┐    process.submit()     ┌──────────┐
│   Lead   │ ──────────────────────▶ │ Worker-A │
│          │ ◀────────────────────── │          │
│          │    process.poll()       │          │
└──────────┘                         └──────────┘

每次多轮交互 = 启动新 -q + --resume 恢复
(不是保持一个长连接，而是每次都新建短命进程恢复同一 session)
```

**实际执行流程（Lead 视角）：**

```python
# 第1轮：初始任务
result = terminal(
    command=f"hermes chat -q '{task_prompt}' -m glm-5.1 --pass-session-id",
    background=True, notify_on_complete=True
)
# → 获取 session_id = "20260512_162849_62f816"

# 第2轮：追加指令（恢复上下文）
result = terminal(
    command=f"hermes chat -q '{followup}' --resume {session_id} -m glm-5.1",
    background=True, notify_on_complete=True
)

# 第N轮：继续...
```

### 3.3 Worker ↔ Worker 通信（邮箱协议）

```
/tmp/team-{team_id}/
├── registry.json          # 团队成员注册表
├── mailbox/
│   ├── worker-a/
│   │   ├── inbox/         # 收件箱（其他 Worker 写入）
│   │   │   └── 001_msg_from_b.json
│   │   └── outbox/        # 发件箱（Worker-A 写入）
│   │       └── 001_reply_to_b.json
│   ├── worker-b/
│   │   ├── inbox/
│   │   └── outbox/
│   └── lead/
│       ├── inbox/         # Worker → Lead 的消息
│       └── outbox/        # Lead → Worker 的指令
└── artifacts/             # 共享产出物
    ├── reports/
    └── code/
```

**消息格式：**
```json
{
  "from": "worker-a",
  "to": "worker-b",
  "type": "request|response|broadcast|alert",
  "subject": "需要你审查 PR #42 的代码",
  "body": "具体内容...",
  "priority": "high|normal|low",
  "timestamp": "2026-05-12T16:30:00Z",
  "reply_to": "001_msg_from_a.json"
}
```

### 3.4 Git Worktree 隔离

```
/Users/can/.hermes/                    # 主工作目录 (Lead)
/Users/can/.hermes/.worktrees/
├── worker-a/                          # Worker-A 独立 worktree
│   └── (git worktree add，独立分支)
├── worker-b/                          # Worker-B 独立 worktree
│   └── (git worktree add，独立分支)
└── worker-c/                          # Worker-C (一次性，用完删除)
    └── (git worktree add，临时分支)
```

**隔离效果：**
- Worker-A 改 `config.yaml`，Worker-B 改 `cli.py`，互不干扰
- Lead 决定何时 merge 各 Worker 的分支
- `--worktree` 参数由 hermes chat 自动创建

---

## 四、任务看板（Beads 集成）

```
┌─────────────────────────────────────────────────────────┐
│                     Beads Issue Tracker                  │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│  Backlog │  Ready   │ In-Prog  │ Review   │   Done      │
├──────────┼──────────┼──────────┼──────────┼─────────────┤
│ task-1   │ task-3   │ task-5   │ task-7   │ task-0      │
│ task-2   │ task-4   │ task-6   │          │ task-1-old  │
│          │          │ ←A       │ ←B审     │             │
└──────────┴──────────┴──────────┴──────────┴─────────────┘

Lead:  bd create → bd claim → 分配给 Worker
Worker: bd show → 实施完成 → bd close
Lead:  bd close 确认 → merge
```

---

## 五、完整工作流示例

### 场景：重构 hermes-agent 配置系统

```
时间线    Lead                                          Workers
──────    ────                                          ────
T0        用户："重构配置系统，拆分大 config.yaml"
T1        bd create 3个子任务:
          - bd-01: 配置 schema 设计
          - bd-02: 迁移脚本编写
          - bd-03: 回归测试
T2        启动 Worker-A (schema设计):
          terminal(bg, "hermes chat -q '你负责 bd-01...'")
          启动 Worker-B (迁移脚本):
          terminal(bg, "hermes chat -q '你负责 bd-02...'")
T3        Worker-A: 执行工具调用，读 config.yaml，设计 schema
          Worker-B: 等待 A 的 schema（通过邮箱轮询 inbox）
T4        Worker-A: 完成设计 → 写入 mailbox/lead/inbox/
          Lead: poll 检测到 → process.submit(followup) 审查
T5        Lead: 审查通过 → process.submit() 通知 A 通知 B
T6        Worker-B: 读取 A 的 schema → 开始写迁移脚本
T7        Worker-B: 完成 → process 退出 → Lead 收到通知
T8        Lead: 启动 Worker-C (一次性 delegate_task)
          delegate_task(goal="运行回归测试...")
T9        Lead: 汇总结果 → 用户汇报
```

---

## 六、技术约束与对策

| 约束 | 影响 | 对策 |
|------|------|------|
| Worker 无 TTY，不能用 `clarify` | 无法实时向用户提问 | ① Worker→Lead 邮箱转发 ② Worker 自行决策+记录日志 |
| `delegate_task` 无 MCP/无 memory | 子任务不能操作 beads/Hindsight | 用 L2 `process+hermes chat` 替代 |
| `delegate_task` 最大 3 并行 | 限制并行度 | L2 Worker 无此限制（受系统资源约束） |
| Worker 每轮是独立进程 | 不是真正的长连接 | 每轮 `--resume` 恢复 session 上下文 |
| hermes chat 启动开销 ~7s | 每轮通信有延迟 | 批量下指令，减少轮次；用 cron 做长周期任务 |
| Git worktree 需要 merge | 并行修改同一文件会冲突 | Lead 协调分工，避免同一文件多人改 |

---

## 七、三层通信协议对比

| 通道 | 方向 | 延迟 | 持久性 | 用途 |
|------|------|------|--------|------|
| `process.submit/poll` | Lead↔Worker | ~7s+ | 进程生命周期 | 紧急指令、实时状态 |
| 邮箱文件 | Worker↔Worker | 轮询间隔 | 磁盘持久 | 跨 Worker 协作、大文件传递 |
| Beads 任务板 | 全局 | ~1s | DB持久 | 任务分配、状态追踪、依赖管理 |
| `cronjob` output | Cron→Lead | 定时触发 | cron log | 定期巡检、数据同步 |

---

## 八、实施清单

### Phase 1：基础框架（1次会话）
- [ ] 编写 `team-init.sh` — 创建 `/tmp/team-{id}/` 目录结构
- [ ] 编写 `registry.json` 模板 — 成员注册/发现
- [ ] 编写邮箱协议工具函数 — send_msg / read_inbox / poll_inbox
- [ ] 验证 `--worktree` + `--resume` 组合使用

### Phase 2：Lead 调度逻辑（1次会话）
- [ ] 编写 Lead 调度 skill — spawn_worker / assign_task / collect_result
- [ ] 编写 Worker 生命周期管理 — 启动/心跳/超时/回收
- [ ] 集成 Beads 任务板 — 自动 create/claim/close

### Phase 3：实战验证（1次会话）
- [ ] 用多 Agent 团队完成一个真实任务
- [ ] 性能测试：3 Worker 并行 vs 单 Agent 串行
- [ ] 产出基准数据

---

## 九、关键验证数据（本次实测）

| 项目 | 结果 | 备注 |
|------|------|------|
| `hermes chat -q "prompt" -m glm-5.1` | ✅ 成功 | 7s 返回，输出答案+session_id |
| `hermes --resume SID -q "next"` | ✅ 成功 | 恢复上下文，继续对话 |
| `--worktree` 隔离 | ✅ 可用 | hermes chat 原生支持 |
| `--pass-session-id` | ✅ 可用 | 输出 session_id 供恢复 |
| `process` 后台管理 | ✅ 可用 | submit/poll/kill/close |
| `delegate_task` | ✅ 可用 | 但无 MCP，仅返回 summary |
| `cronjob` | ✅ 可用 | 独立会话，定时触发 |
| `hermes chat` 交互模式 | ⚠️ 不适用 | Worker 无 TTY，交互模式不可用 |
| `clarify` 在 Worker 中 | ❌ 不可用 | 需要 TTY，Worker 无 TTY |
