# Command Code 深度研究报告

> 研究日期: 2026-05-12 | 版本: v0.25.12 | 来源: 官网 + 文档 + CLI + GitHub

---

## 一、项目概览

**Command Code** — "The coding agent that learns your coding taste"

- **定位**: 首个**持续学习编码偏好**的前沿编码 Agent
- **核心差异化**: `taste-1` 元神经符号AI模型 — 从 accept/reject/edit 信号自动学习开发者偏好
- **版本**: v0.25.12 (npm: `command-code`)
- **CLI命令**: `cmd`（注意：不是 `command`，那是 bash 内建）
- **GitHub**: CommandCodeAI/command-code — 3.2k stars, 328 forks
- **许可**: 源码 bundled/minified，不开源核心实现

### 1.1 技术栈
- Node.js CLI (npm 分发)
- 支持 LLM: Claude, GPT, Kimi, DeepSeek, 开源模型
- 传输: stdio + http (MCP)
- 存储: 本地文件系统 + 远程 commandcode.ai Studio

### 1.2 六大核心特性

| # | 特性 | 一句话 |
|---|------|--------|
| 1 | **Taste 持续学习** | taste-1 RL循环，每次交互自动学习 |
| 2 | **多模式Agent** | Interactive / Headless / Plan / Sandbox |
| 3 | **Skills可扩展** | Agent Skills开放标准(agentskills.io) |
| 4 | **Custom Agents** | 可定义专用子代理(独立上下文+工具集) |
| 5 | **MCP集成** | stdio/http + OAuth + 三级scope |
| 6 | **团队协作** | `npx taste push/pull` + Studio Organizations |

---

## 二、Taste 系统深度剖析

### 2.1 taste-1 算法架构

**元神经符号AI模型 (Meta Neuro-Symbolic AI)**:

```
神经层(Neural): LLM 通用生成能力 — "模型知道什么"
符号层(Symbolic): 用户个体模式与约束 — "模型从你身上学到了什么"
```

**条件生成公式**:
```
// 标准生成
output = LLM(prompt)

// taste-1 条件生成
output = LLM(prompt | taste(user))
```

**不改变模型权重**，而是在推理时通过 `taste(user)` 条件约束重塑输出分布。

### 2.2 持续强化学习循环

```
Generate → Observe → Extract → Learn → Apply → (循环)
  ↓          ↓          ↓         ↓        ↓
生成代码   捕获信号   识别约束   更新taste  下次改进
```

- **实时更新**，无批量训练，每次交互触发
- **自感知的 RL 反馈循环** — "Reflective Context Engineering"

### 2.3 信号收集机制

| 信号 | 含义 | 强度 |
|------|------|------|
| **Accept** | 模式正确 | 正向强化 |
| **Reject** | 模式错误 | 负向强化 |
| **Edit** | 生成与需求的差值(delta) | **最强信号** |

隐式信号: Prompt本身、调试模式、项目上下文

### 2.4 Taste 文件格式

存储为人类可读的 `taste.md`，包含**置信度分数**:

```markdown
## TypeScript
- Use strict mode. Confidence: 0.80
- Prefer explicit return types on exported functions. Confidence: 0.65
- Use type imports for type-only imports. Confidence: 0.90

## Error Handling
- Use typed error classes. Confidence: 0.85
- Always include error codes. Confidence: 0.90
```

- 高置信度 = 跨多个会话的一致行为
- 低置信度 = 仍在形成中
- 可人工检查、编辑或重置

### 2.5 三级存储

| 层级 | 路径 | 用途 |
|------|------|------|
| Project | `.commandcode/taste/` | 特定代码库 |
| Global | `~/.commandcode/taste/` | 跨项目个人偏好 |
| Remote | `commandcode.ai/username/taste` | 团队共享/备份/跨机器 |

### 2.6 CLI 命令

```bash
cmd taste push [pkg] [--all] [-g] [--public] [--overwrite] [--merge]
cmd taste pull <ns/pkg> [-g] [--all] [--overwrite] [--merge]
cmd taste list [-g] [--remote]
cmd taste lint [pkg] [--all] [-g]
cmd taste open [pkg]
cmd taste learn <source>       # 从本地/GitHub仓库学习
```

### 2.7 效果数据

| 任务 | 无Taste | 第1周 | 第1个月 |
|------|---------|-------|---------|
| CLI脚手架 | 4.2次编辑 | 1.8次 | 0.4次 |
| API端点 | 3.1次编辑 | 1.2次 | 0.3次 |
| React组件 | 3.8次编辑 | 1.5次 | 0.5次 |
| 测试文件 | 2.9次编辑 | 0.9次 | 0.2次 |

---

## 三、Skills 系统

### 3.1 遵循开放标准

Command Code 完整实现 [Agent Skills 开放标准](https://agentskills.io)。

### 3.2 SKILL.md 格式

```yaml
---
name: skill-name          # 必需, ≤64字符
description: 描述内容       # 必需, ≤1024字符
license: Apache-2.0       # 可选
compatibility: 环境要求     # 可选
metadata:                  # 可选
  author: example-org
  version: "1.0"
allowed-tools: Read Bash(python:*)  # 实验: 预批准工具
---
```

Body: Markdown指令，推荐 ≤500行。

### 3.3 存储位置（四级优先级）

1. `.commandcode/skills/` (项目)
2. `.agents/skills/` (项目兼容层)
3. `~/.commandcode/skills/` (用户)
4. `~/.agents/skills/` (用户兼容层)

### 3.4 子目录结构

| 目录 | 用途 |
|------|------|
| `scripts/` | 可执行脚本 |
| `references/` | 额外文档(按需加载) |
| `assets/` | 静态资源 |

### 3.5 渐进式披露

1. **发现**: 启动时仅加载 name + description
2. **激活**: 匹配时读取完整 SKILL.md
3. **执行**: 按需加载 references/scripts

### 3.6 调用方式

1. 精确: `/skill-name args`
2. 内联: 提示词中嵌入 `/skill-name`
3. 推断: Agent自动建议

### 3.7 内置13个全局Skills

caveman, diagnose, grill-me, grill-with-docs, improve-codebase-architecture, prototype, setup-matt-pocock-skills, tdd, to-issues, to-prd, triage, write-a-skill, zoom-out

---

## 四、Custom Agents (子代理)

### 4.1 核心概念

每个 Agent 拥有独立的:
- 上下文窗口
- 系统提示词
- 工具集

### 4.2 定义格式

```markdown
---
name: "security-review"
description: "Use for dependency and secret-scanning review before release."
tools: "glob, grep, read_file, think"
---

You are a security-focused reviewer. Prioritize dependency risks...
```

### 4.3 存储位置

| 作用域 | 路径 |
|--------|------|
| 项目级 | `.commandcode/agents/` |
| 个人级 | `~/.commandcode/agents/` |

保留名: explore, plan, review, general (不可覆盖)

---

## 五、Memory 系统

### 5.1 核心设计

基于 `AGENTS.md` 文件 — **纯文本Markdown，无数据库**。

| 作用域 | 路径 |
|--------|------|
| 项目级 | `./AGENTS.md` 或 `.commandcode/AGENTS.md` |
| 用户级 | `~/.commandcode/AGENTS.md` |

### 5.2 特性

- 支持 `@file.md` 语法引用其他文件
- `/init` 自动生成模板
- `/memory` 交互式编辑
- 项目级可 Git 版本控制
- **无自动写入** — 需手动维护

---

## 六、Hooks 钩子系统

### 6.1 事件类型

| 事件 | 时机 | 能否阻止 |
|------|------|----------|
| PreToolUse | 工具执行前 | ✅ |
| PostToolUse | 工具返回后 | ❌ (建议性重试) |

### 6.2 四种响应动作

| 动作 | 说明 |
|------|------|
| Allow | 允许执行 |
| Deny | 阻止执行(仅Pre) |
| Halt | 停止整个会话 |
| Inject Context | 向模型注入额外上下文 |

### 6.3 配置

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "shell|write",
      "hooks": [{
        "type": "command",
        "command": "./hook.sh",
        "timeout": 30
      }]
    }]
  }
}
```

位置: `~/.commandcode/settings.json` (User) / `.commandcode/settings.json` (Project)

### 6.4 工具匹配器

`shell`, `read`, `write`, `edit` — 支持正则、大小写不敏感、多工具匹配

---

## 七、MCP 集成

| Transport | 示例 |
|-----------|------|
| stdio (默认) | `cmd mcp add my-tool -- npx @org/mcp-server` |
| http | `cmd mcp add --transport http notion URL` |

三级 Scope: local > project > user

工具命名: `mcp__<server>__<tool>`
OAuth: `cmd mcp auth <server>`

---

## 八、Studio 平台

- Web管理中心: commandcode.ai
- Profile / Taste Studio / API Keys / Usage & Billing / Settings
- Organizations: 团队共享工作区(独立Profile/Taste/API Keys)
- Taste共享: push → Studio → 队友 pull

---

## 九、CLI 完整命令参考

### 顶层命令

| 命令 | 说明 |
|------|------|
| `cmd` | 启动交互会话 |
| `cmd "message"` | 带初始消息启动 |
| `cmd -c` | 继续上次会话 |
| `cmd -r [name]` | 恢复命名会话 |
| `cmd -p "query"` | 非交互模式 |
| `cmd --plan` | Plan模式启动 |
| `cmd --auto-accept` | 自动接受模式 |
| `cmd --yolo` | 跳过所有权限 |
| `cmd taste` | 管理taste包 |
| `cmd mcp` | 管理MCP服务器 |
| `cmd skills` | 管理skills |
| `cmd login/logout` | 认证 |

### Slash命令

/init, /memory, /resume, /rename, /rewind, /clear, /share, /taste, /learn-taste, /skills, /agents, /mcp, /model, /compact, /context, /ide, /review, /pr-comments, /add-dir, /status, /usage, /help, /exit

### 快捷键

Shift+Tab(模式切换), Ctrl+T(学习反馈), Alt+P(模型切换), Ctrl+G(外部编辑器), Esc×2(回退检查点)

---

## 十、关键发现与对 Hermes 的建议

### 10.1 核心发现

| # | 发现 | 影响 |
|---|------|------|
| F1 | **Taste 是真正的差异化** — 不是 rules/skills 的替代，是第三层"对齐层" | Hermes 缺少此层 |
| F2 | **Skills 遵循开放标准** (agentskills.io) — 格式与 Hermes SKILL.md 高度相似 | 可互操作 |
| F3 | **Hooks 是确定性护栏** — PreToolUse deny 可阻止危险操作 | Hermes 完全没有 |
| F4 | **Custom Agents = 子代理委派** — 独立上下文+工具集 | 对应 Hermes 的 Profile |
| F5 | **Memory 是纯文件** — AGENTS.md + @引用 — 简单但可 Git 共享 | Hermes 的 OpenViking 更强但更复杂 |
| F6 | **渐进式披露** — Skills 发现→激活→执行三阶段 | Hermes 当前全量注入 |
| F7 | **置信度分数** — Taste 学习结果带 0-1 置信度 | Hermes memory 无此概念 |
| F8 | **taste learn** — 可从已有代码库/GitHub 仓库学习 | Hermes 无此能力 |

### 10.2 对 Hermes 的具体建议（按优先级排序）

#### P0: 引入 "Taste" 偏好学习层 ⭐⭐⭐

**问题**: Hermes 的 Skills 告诉 Agent "做什么"，但缺少"你怎么做"的对齐层。

**方案**:
1. 在 `~/.hermes/taste/` 下创建 `taste.md`，格式参考 Command Code
2. 在 `hermes-agent` 的 context 注入中，taste.md 作为**始终注入**的上下文（与 SOUL.md 同级）
3. 利用 Hermes 已有的 Hindsight + OpenViking 记忆系统，从 session 历史中**自动提取偏好信号**：
   - 用户修改了 Agent 输出 → Edit 信号 → 提取约束
   - 用户明确纠正 → Reject 信号 → 负向约束
   - 用户接受无修改 → Accept 信号 → 正向强化
4. 与 Command Code 不同的是，Hermes 可以利用 **Hindsight reflect** 做更深层的偏好推理

**实现路径**:
```
session_end → 检测 edit/correct/accept 信号 → Hindsight reflect 提取偏好 
→ 生成/更新 taste.md 条目(带置信度) → 下次 session 自动注入
```

#### P1: Hooks 确定性护栏系统 ⭐⭐⭐

**问题**: Hermes 完全依赖模型自律来避免危险操作，无法确定性阻止。

**方案**:
1. 在 `config.yaml` 中新增 `hooks` 配置段
2. 实现 `PreToolUse` 和 `PostToolUse` 事件钩子
3. 钩子执行方式: shell command (与 Command Code 一致)
4. stdin/stdout JSON 协议: `{"tool_name":"terminal","tool_input":{"command":"rm -rf /"}}` → `{"decision":"deny","reason":"危险命令"}`
5. 重点应用场景:
   - 阻止 `rm -rf /`、`curl | sh` 等危险 shell 命令
   - 阻止写入敏感路径 (`/etc/`, `/sys/`)
   - 读取 `.env`/`.pem` 时注入脱敏提醒
   - 审计日志: 所有文件写入操作记录到审计文件

#### P2: Skills 渐进式披露优化 ⭐⭐

**问题**: Hermes 当前在 system prompt 中**全量注入**所有 skills 的 name+description，随 skills 数量增长，token 浪费严重。

**方案**:
1. **发现阶段**: 仅注入 skill names + 一句话描述（现状，但需精简）
2. **激活阶段**: 用户输入匹配 trigger 时，才 `skill_view()` 加载完整 SKILL.md
3. **执行阶段**: 按需加载 `references/`, `scripts/`
4. 添加 `allowed-tools` frontmatter 字段：指定该 skill 推荐使用的工具子集

#### P3: Custom Agent (Profile) 能力增强 ⭐⭐

**问题**: Hermes 的 Profile 当前仅有 SOUL.md + personalities，缺少工具集约束和 description 路由。

**方案**:
1. Profile SOUL.md 新增 YAML frontmatter:
   ```yaml
   name: "security-reviewer"
   description: "Use for security audit and vulnerability scanning"
   tools: "read_file, search_files, terminal"  # 限定工具集
   ```
2. Lead Agent 可根据 `description` 自动路由到匹配的 Profile Worker
3. `tools` 限定: Worker 启动时仅暴露指定工具，减少误操作

#### P4: Memory @引用语法 ⭐

**问题**: Hermes 的 OpenViking/Hindsight 记忆系统强大但复杂，AGENTS.md 的 `@file.md` 引用更轻量。

**方案**:
1. 在 `~/.hermes/AGENTS.md` 支持项目级指令文件
2. 支持 `@path/to/file` 语法，会话启动时自动展开
3. 与 OpenViking 互补: AGENTS.md 做项目级硬编码指令，OpenViking 做语义检索

#### P5: taste learn — 从代码库学习 ⭐

**问题**: 新项目没有历史 session，taste 为空。

**方案**:
1. `hermes taste learn <path>` 命令
2. 扫描代码库，用 LLM 分析编码模式、命名约定、架构偏好
3. 自动生成初始 taste.md
4. 可从 GitHub 仓库学习: `hermes taste learn owner/repo`

### 10.3 与 Hermes 现有能力的关系映射

| Command Code | Hermes 对应 | 差距 |
|-------------|------------|------|
| Taste (taste-1) | ❌ 无对应 | **最大差距** — 需P0建设 |
| Skills (SKILL.md) | ✅ Skills 系统 | 格式高度相似，可互操作 |
| Custom Agents | ⚠️ Profile (SOUL.md) | 缺 tools 限定和 description 路由 |
| Memory (AGENTS.md) | ⚠️ OpenViking + Hindsight | OV更强但更复杂，缺@引用和Git共享 |
| Hooks | ❌ 无对应 | **安全差距** — 需P1建设 |
| MCP | ✅ Native MCP client | 基本等价，CC多了OAuth |
| Studio | ❌ 无对应 | 暂不需要（Hermes是自托管） |
| taste push/pull | ⚠️ viking_remember + Git | 需要Taste层先建好 |
| 渐进式披露 | ❌ 全量注入 | 需P2优化 |
| 置信度分数 | ❌ 无 | 需P0引入 |

### 10.4 建议实施路线图

```
Phase 1 (本周): P0 Taste 基础框架
  - ~/.hermes/taste/taste.md 格式定义
  - session_end 信号检测 + 偏好提取
  - context 注入 taste.md

Phase 2 (下周): P1 Hooks 护栏
  - config.yaml hooks 配置段
  - PreToolUse deny/allow 机制
  - 危险命令阻止 + 审计日志

Phase 3 (第3周): P2 渐进式披露 + P3 Profile增强
  - Skills 按需加载优化
  - Profile SOUL.md frontmatter 扩展

Phase 4 (第4周): P4 @引用 + P5 taste learn
  - AGENTS.md @引用语法
  - 从代码库学习 taste
```

---

## 十一、结论

Command Code 最有价值的创新是 **Taste 层** — 在 Rules(约束) 和 Skills(能力) 之上，增加了"对齐"维度。这解决了一个真实痛点：同一个 Skill，不同开发者使用应该产生不同风格的代码。

Hermes 当前在 Skills 和 MCP 上与 Command Code 基本等价，在记忆系统（OpenViking + Hindsight）上甚至更强，但缺少两个关键层：

1. **Taste 偏好学习** — 让 Agent 越用越懂你
2. **Hooks 确定性护栏** — 让 Agent 行为可控可审计

这两个是最值得从 Command Code 借鉴的核心思想，其他特性（渐进式披露、Profile增强、@引用等）为次要优化。
