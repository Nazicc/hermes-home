# Hermes Agent + SkillClaw 融合架构

> 定义：两套系统的边界、协作模式、和集成规范
> 最后更新：2026-05-31

---

## 一、核心架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                    HERMES AGENT (推理层)                          │
│                                                                  │
│  CLI (tui/chat)    Gateway (:8642)    Cron Scheduler             │
│       │                  │                  │                    │
│       └──────────┬───────┘──────────────────┘                    │
│                  │                                                │
│           AIAgent (run_agent.py)                                  │
│            ↕  MCP Client (stdio subprocesses)                     │
│                                                                  │
│  Tools Layer:  File · Terminal · Web · Browser · Delegate       │
│  Skills Layer: ~/.hermes/skills/ (197 skills)                   │
│  State:       ~/.hermes/state.db (SQLite, FTS5)                 │
│  Memory:      SimpleMem (:8420) · Hindsight (:18888) · Memory  │
│  MCP Servers: 15+ (beads, deepcode, deeptutor, deerflow, ...)  │
└──────────────────────────┬────────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           │         API 路由               │
           │   provider: custom             │
           │   base_url: localhost:30000    │
           └───────────────┬───────────────┘
                           │
┌──────────────────────────┴────────────────────────────────────────┐
│                    SKILLCLAW (数据层)                               │
│                                                                   │
│  Proxy Server (port 30000)                                        │
│  ┌─────────────────────────────────────────────┐                  │
│  │ · OpenAI 兼容 API 转发 → DeepSeek            │                  │
│  │ · 会话录制 → ~/.skillclaw/records/          │                  │
│  │ · Skill 引用提取（从 tool calls 中）         │                  │
│  │ · 热重载 (SIGUSR1, API key 轮换)            │                  │
│  │ · 技能路径解析 → ~/.hermes/skills/          │                  │
│  └─────────────────────────────────────────────┘                  │
│                                                                   │
│  Evolve Server (ai.hermes.skillclaw-evolve, 每300s)              │
│  ┌─────────────────────────────────────────────┐                  │
│  │ ① Summarize: 解析会话到技能引用              │                  │
│  │ ② Aggregate: 按 skill 分组会话证据           │                  │
│  │ ③ Execute: LLM 驱动技能演化                  │                  │
│  │    → 写入 ~/.hermes/skills/<skill>/SKILL.md  │                  │
│  └─────────────────────────────────────────────┘                  │
│                                                                   │
│  Key Reloader (com.hermes.skillclaw-key-reloader, 每5s)          │
│  ┌─────────────────────────────────────────────┐                  │
│  │ · 监听 credential pool 输出                  │                  │
│  │ · SIGUSR1 触发 proxy 热重载                  │                  │
│  └─────────────────────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────────┘
```

## 二、核心边界定义

### 边界原则

| 层级 | Hermes 负责 | SkillClaw 负责 |
|------|-------------|----------------|
| **推理** | 对话、工具调用、MCP、记忆检索 | — |
| **路由** | provider 配置 → localhost:30000 | API 转发、限流、重试、记录 |
| **技能** | 技能匹配、加载到 system prompt | 技能创建、演化、质量审计 |
| **会话** | 消息组组织、压缩、search | 会话录制、技能引用提取 |
| **凭证** | 凭证池管理、轮换策略 | 热重载、运行时使用 |
| **部署** | Gateway launchd, TUI, CLI | Proxy launchd, Evolve launchd, Key-reloader launchd |

**一句话规则：** Hermes 是推理引擎，SkillClaw 是数据管道。Hermes 决定问什么，SkillClaw 决定学什么。

## 三、launchd 服务清单（最终版）

> 已合并冗余 plist，消除重复

### 激活的服务

| Label | 程序 | 启动方式 | 端口 | 作用 |
|-------|------|----------|------|------|
| `ai.hermes.gateway` | `hermes gateway run --replace` | KeepAlive | 8642 | Hermes 网关 |
| `ai.hermes.workspace` | `pnpm dev --port 5175` | KeepAlive | 5175 | Hermes Web UI |
| `com.hermes.skillclaw` | `skillclaw proxy` | KeepAlive | **30000** | API 代理 + 会话录制 |
| `ai.hermes.skillclaw-evolve` | `skillclaw evolve` | StartInterval=300 | — | 技能演化管道 |
| `com.hermes.skillclaw-key-reloader` | `python3 key_reloader.py` | KeepAlive | — | 凭证热同步 |
| `com.hermes.skillclaw-proxy` | ❌ **已废弃**（与 com.hermes.skillclaw 重复） | — | — | — |

### 启动顺序依赖

```
boot  →  com.hermes.skillclaw (:30000)  →  ai.hermes.gateway (:8642)
                                        →  ai.hermes.skillclaw-evolve
                                        →  com.hermes.skillclaw-key-reloader
```

**关键规则：** SkillClaw proxy 必须先于 Hermes gateway 启动。Hermes 连不上 :30000 会降级到 fallback_providers。

## 四、SkillClaw 的六大核心功能

### 1. API 代理（核心职责）

```yaml
# ~/.skillclaw/config.yaml
proxy:
  host: 0.0.0.0
  port: 30000
  served_model_name: deepseek-v4-flash  # 对外暴露的模型名
```

- 标准 OpenAI `/v1/chat/completions` 接口
- 自动记录所有会话到 `~/.skillclaw/records/conversations.jsonl`
- 从 tool_calls 中提取技能引用路径
- 支持 API key 热重载（SIGUSR1）

### 2. 会话录制与分析

每一次 Hermes 对话通过 proxy 时，SkillClaw 自动：
- 记录每条消息（user/assistant/tool）
- 提取 tool_call 中的 skill 引用
- 标准化消息格式供 evolve 管道使用
- 分类 turn types（用户指令、工具调用、回退、错误等）

### 3. 技能演化管道

每 300 秒运行的自动学习循环：

```
[新会话] → [Summarize] → [Aggregate by skill] → [Execute]
                                                     ↓
                                         更新 SKILL.md 内容
                                             或创建新 skill
```

**决策维度：**
- 会话证据是否足够（push_min_injections: 5）
- 演化效果是否有提升（push_min_effectiveness: 0.3）
- 是否和现有 skill 冲突

### 4. 技能引用追踪

从 Hermes 的 tool_calls 中智能提取技能引用：

```python
# api_server.py 中的核心逻辑
_extract_skill_names()        # 从 tool args 提取 skill 名
_extract_modified_skill_names()  # 检测被修改的技能
_extract_skill_paths_from_tool_call()  # 解析文件路径
```

识别方式（按优先级）：
1. `skill_manage(action='patch', name='xxx')` → 技能名
2. `skill_view(name='xxx')` → 技能名
3. `read_file('...skills/xxx/...')` → 解析 path 中的技能名
4. `write_file('...skills/xxx/...')` → 同上

### 5. 凭证热同步

```
Hermes credential_pool.py  →  共享 key 文件  →  key_reloader  →  SIGUSR1  →  proxy 热重载
   (round_robin 轮换)       (current_minimax_key)  (5s 轮询)                     (无缝切换)
```

### 6. 技能共享（多 agent 协作）

```yaml
sharing:
  backend: local          # 本地共享
  group_id: hermes-team   # 组标识
  push_min_effectiveness: 0.3
  push_min_injections: 5
  local_root: ~/.skillclaw/shared/
```

所有演化后的技能 → `~/.skillclaw/shared/hermes-team/skills/` → Hermes 自动获取

## 五、Hermes 侧的集成点

### Config 配置

```yaml
# ~/.hermes/config.yaml 相关配置
provider: custom
custom_endpoint: http://localhost:30000  # → SkillClaw proxy

# 备用（SkillClaw 挂了直接走）
fallback_providers:
  - provider: openai
    api_key: sk-...
    base_url: https://api.deepseek.com
    model: deepseek-v4-flash

# 技能目录与 SkillClaw 共享
skills:
  external_dirs:
    - ~/.skillclaw/shared/hermes-team/skills/
```

### 技能匹配

Hermes 在系统提示中使用 `skill_tool.py` 解析技能：
1. 扫描 `~/.hermes/skills/` 中所有 SKILL.md
2. 匹配 YAML frontmatter 的 name/description/trigger
3. 注入匹配的技能到 system prompt
4. SkillClaw evolve 定期更新这些 SKILL.md

## 六、数据流全景

```
                     用户输入
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│  Hermes Agent                                       │
│  · 组装 system prompt（含匹配的技能 + 记忆）          │
│  · 调用 LLM → POST /v1/chat/completions             │
│  · 解析工具调用 → 执行 → 返回结果                    │
│  · 保存到 state.db                                   │
└─────────────────────┬───────────────────────────────┘
                      │  HTTP Request (with Hermes session info)
                      ▼
┌─────────────────────────────────────────────────────┐
│  SkillClaw Proxy (:30000)                           │
│  · 记录请求/响应到 conversations.jsonl              │
│  · 提取 tool_call 中的 skill 引用                    │
│  · 转发请求到 DeepSeek API                          │
│  · 返回响应到 Hermes                                │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  SkillClaw Evolve (every 300s)                      │
│  · 读取新会话记录                                    │
│  · 按技能聚合会话证据                                 │
│  · LLM 驱动：改进 or 创建 skill                      │
│  · 写入 ~/.hermes/skills/ + 共享目录                 │
└─────────────────────────────────────────────────────┘
                      │  新/更新后的 SKILL.md
                      ▼
┌─────────────────────────────────────────────────────┐
│  下次会话：Hermes 使用更新后的 skill                 │
│  → 更精准的任务指导 → 更好的回复                     │
└─────────────────────────────────────────────────────┘
```

## 七、故障恢复策略

### 7.1 SkillClaw Proxy 挂了

```
症状: Hermes API 超时 / connection refused
影响: 所有推理请求失败
恢复: launchd KeepAlive 自动重启
降级: fallback_providers 直接连 DeepSeek（无会话录制）
检查: curl -s http://localhost:30000/v1/models
```

### 7.2 SkillClaw Evolve 挂了

```
症状: 技能不再自动进化
影响: 不影响当前推理，长期影响技能质量
恢复: launchd StartInterval 自动重试
检查: tail ~/.skillclaw/logs/evolve-server.err.log
```

### 7.3 Key Reloader 挂了

```
症状: API key 轮换后 proxy 仍用旧 key
影响: 不影响当前推理（已有 key 继续工作）
恢复: launchd KeepAlive 自动重启
检查: tail ~/.skillclaw/logs/reloader.out.log
```

### 7.4 Hermes Gateway 挂了

```
症状: Feishu/Telegram 无响应
影响: 所有平台消息丢失
恢复: launchd KeepAlive 自动重启
注意: 重启后先确认 SkillClaw proxy 已在运行
检查: curl -s http://localhost:8642/health
```

### 7.5 全部挂了（重启/宕机后）

```
恢复顺序:
  1. wait_port 30000 (SkillClaw proxy)
  2. wait_port 8642   (Hermes gateway)
  3. 检查 evolve 和 key-reloader
```

## 八、运维命令速查

### 状态检查

```bash
# 全系统状态
launchctl list | grep -E "hermes|skillclaw"

# 端口监听
lsof -i :30000 -i :8642 -i :9119 -i :5175

# 技能质量
hermes skills quality        # 查看技能评分分布
curl -s http://localhost:30000/healthz

# Evolve 管道健康
tail -n 20 ~/.skillclaw/logs/evolve-server.out.log
tail -n 20 ~/.skillclaw/logs/evolve-server.err.log

# 会话记录量
wc -l ~/.skillclaw/records/conversations.jsonl
```

### 启动/停止

```bash
# 启动全部（按顺序）
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hermes.skillclaw.plist
sleep 2
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.gateway.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.skillclaw-evolve.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hermes.skillclaw-key-reloader.plist

# 停止全部
for plist in skillclaw gateway skillclaw-evolve skillclaw-key-reloader workspace; do
  launchctl bootout gui/$(id -u)/com.hermes.$plist.plist 2>/dev/null
  launchctl bootout gui/$(id -u)/ai.hermes.$plist.plist 2>/dev/null
done
```

### 故障排查

```bash
# 快速自检脚本
python3 -c "
import httpx
for name, port in [('SkillClaw', 30000), ('Gateway', 8642), ('Dashboard', 9119), ('Workspace', 5175)]:
    try:
        r = httpx.get(f'http://localhost:{port}/healthz', timeout=3)
        print(f'✅ {name} (:{port}) — {r.status_code}')
    except Exception as e:
        print(f'❌ {name} (:{port}) — {e}')
"
```

## 九、SkillClaw 能力分类（与 Hermes 对比）

| 能力 | Hermes 原生 | SkillClaw 增强 | 备注 |
|------|------------|----------------|------|
| LLM 推理 | ✅ AIAgent loop | — | Hermes 核心 |
| 工具调用 | ✅ 15+ 工具 types | — | MCP + 内置 |
| MCP 服务器 | ✅ 原生客户端 | — | Hermes 管理生命周期 |
| 技能匹配 | ✅ 前匹配 + 加载到 prompt | — | |
| 技能演化 | ❌ | ✅ Summarize→Aggregate→Execute | SkillClaw 独有 |
| 会话录制 | ❌ (仅 state.db) | ✅ 语义化 recording | 为演化提供数据 |
| 技能引用追踪 | ❌ | ✅ tool_call 解析 | 自动发现新技能 |
| API 热重载 | ❌ | ✅ SIGUSR1 + 密钥轮换 | 零中断 |
| 凭证池管理 | ✅ round_robin | — | Hermes 独有 |
| 多 agent 共享 | ❌ | ✅ team sharing | |
| 技能质量评分 | ✅ (skills-quality MCP) | ❌ (消费结果) | Hermes 独有 |

## 十、演进路线

### 当前状态 (Phase 0)
- ✅ SkillClaw proxy 运行中（端口 30000，DeepSeek 路由）
- ✅ Evolve 服务器运行中（每 300s 自动演化）
- ✅ Key reloader 运行中（凭证热同步）
- ✅ Hermes gateway 运行中（Feishu/Telegram 平台）
- ✅ 启动顺序正确

### 待优化项
1. **监控统一化**：目前两个系统各自打日志，缺少统一的健康看板
2. **技能质量闭环**：Hermes skills-quality MCP 评分 → SkillClaw evolve 应参考评分结果决定演化优先级
3. **会话数据的双向同步**：SkillClaw 从 proxy 记录会话，但 Hermes 的 state.db 更完整（含 token 统计、end_reason），evolve 管道应联合查询
4. **冗余 plist 清理**：com.hermes.skillclaw-proxy.plist 已废弃，应删除
5. **日志轮转**：当前日志无限增长，需要 logrotate 规则

---

*文档由 Hermes Agent 分析生成，基于本地部署的两套系统实际状态。*
