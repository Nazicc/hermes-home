# Hermes 多 Agent 团队协作方案 v2

> 日期: 2026-05-12
> 基础: Hermes 官方 Profile 机制 + delegate_task + git worktrees
> 融合: Claude Code Agent Teams 五大设计理念

---

## 一、设计理念（来自 Claude Code Agent Teams，映射到 Hermes）

| # | Claude Code 理念 | Hermes 原生映射 |
|---|---|---|
| 1 | **独立进程实例** — 每个 Agent 是独立 OS 进程 | `hermes profile create` → 每个 Profile = 独立进程+独立状态 |
| 2 | **协议化共享状态** — 通过文件/协议而非内存共享 | Beads(任务板) + Mailbox(邮箱) + Git(代码) + Honcho(记忆) |
| 3 | **Lead = 调度者** — 拆解→分配→审查→合并 | Lead 用 `delegate_task`/`process` 编排，不亲自干活 |
| 4 | **自组织+人在环** — Worker 可自主推进，人可随时介入 | Worker 自主执行+邮箱报告；Lead 随时 `--resume` 接管 |
| 5 | **嵌入式质量门** — 每个 Worker 自带检查，不是事后 QA | SOUL.md 内置质量指令 + Beads acceptance criteria + self-test 步骤 |

---

## 二、四层 Agent 体系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  L0  Lead (你当前对话)                                                      │
│  身份: 默认 Profile (default)                                               │
│  职责: 用户交互 · 任务拆解 · 质量审查 · 合并决策                               │
│  工具: 全部 157 tools + 9 MCP + 106 skills + clarify + memory              │
├─────────────────────────────────────────────────────────────────────────────┤
│  L1  Specialist Profiles — 长期队友                                         │
│  身份: `hermes profile create <name> --clone`                               │
│  特征: 独立 SOUL.md · 独立 .env · 独立 state.db · 独立 gateway               │
│  生命周期: 跨会话持久，直到 `hermes profile delete`                            │
│  通信: `hermes -p <name> chat -q` 或 邮箱 或 Beads                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  L2  Delegate Sub-agents — 临时兵                                           │
│  身份: `delegate_task` 进程内子代理                                           │
│  特征: 无 MCP · 无 memory · 无 clarify · 仅返回 summary                      │
│  生命周期: 一次性，跑完即销毁                                                 │
│  通信: 仅返回最终结果给 Lead                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  L3  Cron Patrol — 定时哨兵                                                 │
│  身份: `cronjob` 定时任务                                                    │
│  特征: 独立会话 · 全工具 · 可挂 skill · 可指定 provider                       │
│  生命周期: 按调度周期运行                                                     │
│  通信: cron output → Lead (自动投递到聊天)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、L1 Specialist Profile — 核心设计

### 3.1 创建 Profile（团队建制）

```bash
# 1. 创建 Coder Profile — 专注编码
hermes profile create coder --clone
# → ~/.hermes/profiles/coder/ 独立目录
# → ~/.local/bin/coder 命令别名

# 2. 创建 Reviewer Profile — 专注审查
hermes profile create reviewer --clone

# 3. 创建 Researcher Profile — 专注调研
hermes profile create researcher --clone

# 4. 配置每个 Profile 的身份
echo "# Coder\n你是专注编码的 Worker。只写代码，不写文档。遵循 TDD。每次提交前 self-test。" \
  > ~/.hermes/profiles/coder/SOUL.md

echo "# Reviewer\n你是严格的代码审查者。关注：安全漏洞、性能问题、设计缺陷。给出明确的 LGTM 或 Request Changes。" \
  > ~/.hermes/profiles/reviewer/SOUL.md

echo "# Researcher\n你是调研专家。深度搜索、交叉验证、结构化报告。区分事实与推测。" \
  > ~/.hermes/profiles/researcher/SOUL.md

# 5. 设置工作目录（指向项目代码）
coder config set terminal.cwd /path/to/project
reviewer config set terminal.cwd /path/to/project
researcher config set terminal.cwd /path/to/project
```

### 3.2 Profile 的独立性与隔离

| 维度 | 每个 Profile 独立拥有 |
|---|---|
| 配置 | `config.yaml` — 可设不同模型、工具集、provider |
| 凭证 | `.env` — 可设不同 API key（避免 rate limit 互相影响） |
| 身份 | `SOUL.md` — 决定角色行为（编码者 vs 审查者 vs 调研者） |
| 记忆 | `MEMORY.md` + `USER.md` — 各自积累各自的偏好 |
| 会话 | `state.db` — 会话历史完全隔离 |
| 技能 | `skills/` — 可按角色裁剪 |
| 定时任务 | cron jobs — 各自独立 |
| Gateway | 独立进程 + 独立 bot token（可接入不同平台频道） |
| Honcho AI Peer | Profile 创建时自动生成独立 peer（如启用 Honcho） |

### 3.3 调用 Profile 的 3 种方式

```bash
# 方式 A: 命令别名（最简洁）
coder chat -q "实现 bd-01 的 schema 设计" -m glm-5.1 --pass-session-id

# 方式 B: -p 标志
hermes -p reviewer chat -q "审查最近的 commit" -m glm-5.1 --pass-session-id

# 方式 C: Lead 通过 terminal(background) 驱动
terminal(command="hermes -p researcher chat -q '调研 GLM-5.1 的 function calling 限制' -m glm-5.1 --pass-session-id",
         background=true, notify_on_complete=true)
```

### 3.4 多轮协作 = `--resume` 链

```bash
# Round 1: 分配任务
coder chat -q "实现 bd-01: 设计配置 schema" -m glm-5.1 --pass-session-id
# → 输出答案 + session_id: "20260512_170000_abc123"

# Round 2: Lead 审查后追加修改意见
coder chat -q "schema 缺少 validation 字段，请补充" --resume 20260512_170000_abc123 -m glm-5.1

# Round 3: 请求自测
coder chat -q "运行 pytest 验证你的改动" --resume 20260512_170000_abc123 -m glm-5.1
```

---

## 四、共享状态协议 — 4 个通道

### 4.1 Beads 任务板（主通道 — 任务状态）

```
Lead                          Workers
────                          ───────
bd create "bd-01: schema"  →  
bd create "bd-02: migrate" →  
bd create "bd-03: test"    →  
                              coder:    bd claim bd-01 → bd show → 实现 → bd close
                              coder:    bd claim bd-02 → bd show → 实现 → bd close
                              reviewer: bd claim bd-03 → bd show → 审查 → bd close
```

**优势：** 依赖管理（bd-03 blocks-on bd-01）、优先级排序、原子 claim（防重复领取）

### 4.2 邮箱协议（Worker ↔ Worker 协作）

```
~/.hermes/team-{id}/mailbox/
├── coder/
│   ├── inbox/       # reviewer 写入审查意见
│   └── outbox/      # coder 写入完成通知
├── reviewer/
│   ├── inbox/       # coder 写入审查请求
│   └── outbox/      # reviewer 写入审查结果
└── lead/
    ├── inbox/       # Worker → Lead 的报告/问题
    └── outbox/      # Lead → Worker 的指令
```

**何时用邮箱而非 Beads：**
- Worker 间传递非结构化数据（文件路径、配置片段、中间结果）
- 紧急通信（不需要走完整的 issue 流程）
- 大块内容（代码片段、日志输出）

### 4.3 Git Worktrees（代码隔离）

```
/project-repo/                    # Lead 的工作目录
/project-repo/.worktrees/
├── coder/                        # coder Profile 的 worktree (分支: feat/coder-bd01)
├── reviewer/                     # reviewer Profile 的 worktree (分支: feat/reviewer-bd03)
└── temp-research/                # researcher 临时 worktree (用完删除)
```

**操作流程：**
```bash
# Worker 在自己 worktree 上工作（互不冲突）
coder chat -q "在 worktree 上实现 bd-01，提交到 feat/coder-bd01 分支" --worktree

# Lead 审查后合并
git checkout main
git merge feat/coder-bd01
git merge feat/reviewer-bd03
```

### 4.4 Honcho 共享记忆（跨 Profile 上下文）

```
┌───────────┐     ┌──────────────┐     ┌───────────┐
│   coder   │────▶│   Honcho     │◀────│ reviewer  │
│ (peer-a)  │     │  Workspace   │     │ (peer-b)  │
└───────────┘     │  (shared)    │     └───────────┘
                  │              │
                  │ • 结论共享    │
                  │ • 语义搜索    │
                  │ • 会话总结    │
                  └──────────────┘
```

**配置要点：**
- 每个 Profile 自动获得独立 AI Peer（`--clone` 时创建）
- 同一个 Workspace → 共享 Conclusions（结论）
- `recallMode: hybrid` → 自动注入相关上下文 + 手动搜索工具

---

## 五、完整编排模式

### 模式 1: 并行分工（最常用）

```
用户: "重构配置系统"
                │
    Lead: bd create 3 个子任务 (bd-01, bd-02, bd-03)
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
  coder      coder      researcher
  (bd-01)    (bd-02)    (bd-03: 调研先)
    │           │           │
    │           │     完成→写邮箱→
    ▼           ▼           │
  自测通过    自测通过       │
    │           │           │
    └─────┬─────┘           │
          ▼                 │
    reviewer ←──────────────┘
    (审查所有改动 + 调研结论)
          │
          ▼
    Lead: merge + push
```

**执行代码：**
```bash
# Step 1: Lead 创建任务
bd create "bd-01: 配置 schema 设计" --priority 2
bd create "bd-02: 迁移脚本" --priority 2 --deps bd-01
bd create "bd-03: 调研其他项目方案" --priority 1

# Step 2: 启动并行 Worker
terminal(background=true, notify_on_complete=true,
  command="hermes -p researcher chat -q 'bd claim bd-03，然后执行调研，结果写入 mailbox/coder/inbox/001_research.json' -m glm-5.1 --pass-session-id")

terminal(background=true, notify_on_complete=true,
  command="hermes -p coder chat -q '等 bd-03 完成后 bd claim bd-01，基于调研结果设计 schema，完成后 bd close' -m glm-5.1 --pass-session-id")

# Step 3: bd-01 完成后启动 bd-02
terminal(background=true, notify_on_complete=true,
  command="hermes -p coder chat -q 'bd claim bd-02，基于 bd-01 的 schema 写迁移脚本，self-test 后 bd close' -m glm-5.1 --pass-session-id")

# Step 4: 全部完成后审查
terminal(background=true, notify_on_complete=true,
  command="hermes -p reviewer chat -q '审查 feat/coder-* 的所有改动，检查安全和性能，给出 LGTM 或 Request Changes' -m glm-5.1 --pass-session-id")
```

### 模式 2: 流水线（依赖链）

```
researcher → coder → reviewer → Lead(merge)
   T0-T5      T5-T10   T10-T12   T12
```

Beads `deps` 自动阻塞：bd-02 blocks-on bd-01 → Worker claim bd-02 时发现 blocked → 等待。

### 模式 3: 对抗审查（质量提升）

```
coder 写代码 → reviewer 挑错 → coder 修复 → reviewer 再审 → LGTM
```

两个 Profile 用对立 SOUL.md：
- coder: "追求效率，快速实现"
- reviewer: "追求质量，宁可过度审查也不放过问题"

### 模式 4: 临时增援（delegate_task）

```
Lead: "这个子任务只需要搜索 3 个网页，不值得启动 Profile"
→ delegate_task(goal="搜索 X/Y/Z", toolsets=["web"])
→ 3 路并行，30s 内全部返回
```

---

## 六、Profile 模板

### 6.1 Coder Profile

```yaml
# ~/.hermes/profiles/coder/SOUL.md
# Coder — 专注实现

你是一名专注编码的 Worker。

## 行为准则
- 只写代码和测试，不写长文档
- 每次 commit 前必须 self-test（pytest/make test）
- 遇到不确定的设计决策，写入邮箱 `lead/inbox/` 等待指示
- 不要自行 merge 到 main，只提交到 `feat/<task-id>` 分支
- 完成任务后 `bd close` 并通知邮箱

## 质量门
- [ ] 代码通过 lint
- [ ] 测试覆盖新逻辑
- [ ] 无 hard-coded 密钥
- [ ] 错误处理完善
```

```yaml
# ~/.hermes/profiles/coder/config.yaml (差异部分)
agent:
  personalities:
    coding: "快速、精准、测试优先"
terminal:
  cwd: /path/to/project
```

### 6.2 Reviewer Profile

```yaml
# ~/.hermes/profiles/reviewer/SOUL.md
# Reviewer — 严格审查

你是一名严格的代码审查者。

## 行为准则
- 只审查，不实现
- 每个审查项必须给出明确的 LGTM / Request Changes
- 重点关注：安全漏洞、性能瓶颈、设计缺陷、测试遗漏
- 审查结果写入 `outbox/` + `bd close` 时附审查意见
- 发现 critical 问题立即写入 `lead/inbox/` 标记 priority=high

## 审查清单
- [ ] 输入验证
- [ ] 错误处理
- [ ] 资源泄漏
- [ ] 性能影响
- [ ] 向后兼容
```

### 6.3 Researcher Profile

```yaml
# ~/.hermes/profiles/researcher/SOUL.md
# Researcher — 深度调研

你是一名调研专家。

## 行为准则
- 搜索至少 3 个来源，交叉验证
- 区分"事实"与"推测"，标注置信度
- 输出结构化报告（结论→证据→来源）
- 调研结果写入 `mailbox/` 供其他 Worker 消费
- 不修改任何代码
```

---

## 七、通信协议详细规范

### 7.1 邮箱消息格式

```json
{
  "msg_id": "001",
  "from": "coder",
  "to": "reviewer",
  "type": "request",
  "subject": "请审查 feat/coder-bd01 的改动",
  "body": "bd-01 已完成，包含 3 个文件修改。请重点审查 config/schema.py 的验证逻辑。",
  "priority": "normal",
  "timestamp": "2026-05-12T17:00:00Z",
  "reply_to": null,
  "artifacts": ["/path/to/diff.patch"]
}
```

### 7.2 团队注册表

```json
// ~/.hermes/team-{id}/registry.json
{
  "team_id": "config-refactor-20260512",
  "created_at": "2026-05-12T16:00:00Z",
  "members": {
    "lead": {
      "profile": "default",
      "session_id": "current",
      "status": "active"
    },
    "coder": {
      "profile": "coder",
      "session_id": "20260512_170000_abc123",
      "status": "working",
      "assigned_tasks": ["bd-01", "bd-02"]
    },
    "reviewer": {
      "profile": "reviewer",
      "session_id": "20260512_170500_def456",
      "status": "idle",
      "assigned_tasks": []
    }
  },
  "beads_workspace": "/path/to/project"
}
```

### 7.3 心跳机制

```bash
# Worker 每轮 --resume 时自动更新 registry.json 的 last_seen
# Lead 定期检查：
for member in registry.members; do
  if now - member.last_seen > 10min:
    alert("Worker $member 可能卡住")
fi
done
```

---

## 八、与 Claude Code Agent Teams 的理念对照

| 理念 | Claude Code 实现 | Hermes 实现 | 优势 |
|---|---|---|---|
| 独立进程 | `claude --agent` | `hermes profile create` | Profile 有完整状态隔离，不只是进程隔离 |
| 共享状态 | Git + 文件系统 | Git + Beads + 邮箱 + Honcho | 4 通道 vs 2 通道，任务/记忆/代码/消息全覆盖 |
| Lead 调度 | 主 Agent 拆解分发 | Lead 用 delegate_task + process 编排 | delegate_task 无 MCP 限制 → 改用 Profile 调用 |
| 人在环 | /bg 运行，人可查看 | `--resume` 随时接管 + clarify | Lead 有 clarify，可实时与用户交互 |
| 质量门 | Agent 自带 test 指令 | SOUL.md 内置 + Beads acceptance + self-test | 三层质量门：身份级 + 任务级 + 自动化级 |

**Hermes 的独特优势：**
1. **Profile 是一等公民** — Claude Code 没有等价概念，每个 agent 只是进程
2. **Honcho 共享记忆** — 跨 Profile 的语义搜索 + 结论共享，Claude Code 无此机制
3. **Beads 原生集成** — 任务依赖、原子 claim、优先级排序，无需外挂
4. **Token 锁** — 防止两个 Profile 用同一个 bot token 冲突
5. **Profile export/import** — 整个团队配置可打包迁移

---

## 九、实施路线

### Phase 1: 建制（30 min）

- [ ] `hermes profile create coder --clone`
- [ ] `hermes profile create reviewer --clone`
- [ ] `hermes profile create researcher --clone`
- [ ] 写入 3 个 SOUL.md
- [ ] 验证 `coder chat -q "hello"` 正常工作

### Phase 2: 通信（30 min）

- [ ] 创建 `~/.hermes/team/` 目录结构
- [ ] 编写 `registry.json` 模板
- [ ] 编写邮箱工具函数（send_msg / read_inbox / poll_inbox）
- [ ] 验证 Worker 间邮箱通信

### Phase 3: 编排（30 min）

- [ ] 编写 Lead 编排 skill（spawn / assign / collect / review）
- [ ] 集成 Beads 任务板
- [ ] 验证 `--resume` 多轮协作
- [ ] 验证 `--worktree` 代码隔离

### Phase 4: 实战（1 session）

- [ ] 用多 Agent 团队完成一个真实任务
- [ ] 性能对比：3 Profile 并行 vs 单 Agent 串行
- [ ] 产出基准数据

---

## 十、技术约束与对策

| 约束 | 影响 | 对策 |
|---|---|---|
| `hermes chat -q` 每轮 ~7s 启动 | 多轮通信有延迟 | 批量下指令减少轮次；重活单轮完成 |
| Worker 无 TTY，不能用 `clarify` | 无法实时向用户提问 | 邮箱转发 → Lead clarify → 回传 |
| `delegate_task` 无 MCP/memory | 不能操作 beads/Hindsight | Profile 调用替代 delegate_task |
| Profile 共享文件系统 | 潜在文件冲突 | Worktree 隔离 + Lead 协调分工 |
| Profile 数量无硬限制 | 资源竞争 | 合理控制并发（建议 ≤ 3 同时活跃） |
| Honcho 需要配置 | 跨 Profile 记忆需 Honcho | `--clone` 自动创建独立 peer |
