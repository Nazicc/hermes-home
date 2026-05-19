---
name: caveman
description: "使 Hermes Agent 用\"原始人语言\"压缩输出，减少 ~75% token 消耗。触发词：caveman、压缩输出、话太多、简洁点、说人话、原始人模式。路径：~/.hermes/skills/skills/caveman/SKILL.md。版本：caveman v1.0.0 | Claude Code 原始人风格适配到 Hermes Agent | 2025-05-03。NOT for: Claude Code 用户（应使用原始 caveman 插件）、非 markdown 文件压缩（代码文件跳过）。"
category: general
---

---
name: caveman
description: >
  使 Hermes Agent 用"原始人语言"压缩输出，减少 ~75% token 消耗。
  触发词：caveman、压缩输出、话太多、简洁点、说人话、原始人模式。
  路径：~/.hermes/skills/skills/caveman/SKILL.md
  版本：caveman v1.0.0 | Claude Code 原始人风格适配到 Hermes Agent | 2025-05-03
---

# Caveman Mode — Hermes Agent

> ⚡ **Caveman Mode**: 强制压缩输出，用原始人风格说话。

压缩输出示例（caveman ultra 规则）：

[原始]: This is a test message that demonstrates the compression effect.
[压缩]: test msg: demonstrates compression effect.

[原始]: I would like to request that you please implement this feature as soon as possible.
[压缩]: pls implement this feature ASAP.


## 触发条件（什么时候该激活）

满足以下任一条件时，激活 caveman mode：
- 用户明确要求压缩/简洁/原始人/话太多/说人话
- 对话已超过 30 轮（防止 context 爆炸）
- 用户在用中文沟通（压缩中文比压缩英文更有效）
- 调用 skill 时指定了 `/caveman`
- 标记了 `mode=caveman` 的 cron 任务
- `~/.config/caveman/config.json` 存在且 `defaultMode` 非空

## 强度等级

| 等级 | 适用场景 | 示例输出 |
|---|---|---|
| `lite` | 正式报告 / PR review / code review | This implements X. |
| `full` | 日常对话（默认） | implements X. |
| `ultra` | 极端 context 压力 / 超长对话 | impl X. |

压缩规则（按激进程度）：
1. **Drop filler**: 去除 `I think`, `I believe`, `of course`, `basically`, `actually`, `you know`, `well`, `so`, `just`, `that`, `please`, `kind of`, `sort of`
2. **Drop articles**: 去除 `the`, `a`, `an`
3. **Drop pronouns**: 去除 `I`, `you`, `we`（主语上下文清楚时）
4. **Shorten phrases**: `in order to` → `to`, `due to the fact that` → `because`, `at this point in time` → `now`
5. **Shorten tech phrases**: `please implement` → `impl`, `would like to` → `-`, `as soon as possible` → `ASAP`, `in the event that` → `if`
6. **Shorten common phrases**: `machine learning` → `ML`, `artificial intelligence` → `AI`, `natural language processing` → `NLP`, `large language model` → `LLM`, `artificial intelligence` → `AI`
7. **Ultra only — aggressive**: `for example` → `e.g.`, `that is to say` → `i.e.`, `with regard to` → `re`, `due to` → `cuz`, `without loss of generality` → `WLOG`, `information` → `info`

## 输出格式（caveman 响应模板）

### 基本格式

❯ **<意图标签>** <caveman 风格响应>

<补充信息（如有）>


❯ **分析**: impl the feature.
❯ **操作**: rm -rf cache dir.

### 长输出格式（超过 3 行）

❯ **<意图标签>**
<caveman 风格响应>

**补充**：<caveman 格式的补充说明>


## 文件压缩流程

当用户要求压缩文件（`/caveman:compress <文件路径>`）时：

1. 读取文件内容
2. 识别文件类型（代码跳过，仅压缩 `.md/.txt/.markdown/.rst`）
3. 用 MiniMax API 压缩为 caveman 风格（见下方压缩 prompt）
4. 备份原文件为 `*.original.md`
5. 覆盖写入压缩版本

> ⚠️ **安全过滤**（始终执行）：
> - 跳过 `.env`, `credentials.*`, `secrets.*`, `*.pem`, `*.key`, `.ssh/`, `.aws/`, `.gnupg/`
> - 如果文件路径包含敏感关键词（api_key, password, token, secret）则跳过压缩

### 压缩 Prompt（用于 MiniMax API 调用）


You are a compression expert. Compress this markdown to caveman style while preserving key information:
- Drop articles: the, a, an
- Drop pronouns: I, you, we (when contextually clear)
- Drop filler: I think, I believe, of course, basically, actually, you know, well, so, just, that
- Shorten phrases: in order to → to, due to the fact that → because, at this point in time → now
- Shorten tech: please implement → impl, would like to → -, as soon as possible → ASAP
- Abbreviate: machine learning → ML, natural language processing → NLP, large language model → LLM
- Ultra mode only: for example → e.g., that is to say → i.e., information → info
- Preserve ALL code blocks, file paths, commands, URLs, technical terms as-is
- Preserve frontmatter metadata
- Preserve section headers (##, ###)
- Preserve critical technical details (API endpoints, function names, config keys)

Input:
<file content>

Output: ONLY the compressed markdown, no explanations, no preamble.


### 不压缩
`.py`, `.js`, `.ts`, `.json`, `.yaml`, `.yml`, `.toml`, `.env`, `.lock`, `.css`, `.html`, `.xml`, `.sql`, `.sh`, `.go`, `.rs`, `.java`, `.c`, `.cpp`, `.h`, `.hpp`, `.rb`, `.php`, `.swift`, `.kt`, `.lua`, `.dockerfile`, `.makefile`, `.csv`, `.ini`, `.cfg`, `.md`（此文件本身）

## Hermes Agent 集成

### 安装后必做
bash
# 删除 skills 快照缓存（强制重建索引）
rm -f ~/.hermes/.skills_prompt_snapshot.json

不删除则新 skill 不出现。

### 配置文件

~/.config/caveman/config.json


{
  "defaultMode": "full",
  "compressBackup": true,
  "compressScriptsPath": "~/.claude/plugins/marketplaces/caveman/caveman-compress/scripts",
  "hermesIntegration": true
}


### Skill 触发方式

1. **自动触发**：用户消息含 caveman 关键词 → 自动激活输出压缩
2. **手动触发**：调用 skill 时指定 `/caveman` → 激活输出压缩
3. **文件压缩**：`/caveman:compress <path>` → 压缩指定文件
4. **强度切换**：`/caveman:level <lite|full|ultra>` → 改变压缩强度
5. **禁用**：说「恢复正常」、「verbose mode」→ 退出 caveman mode

### 已知限制

1. **MiniMax API 限速**：压缩调用可能因 API 限速失败，重试即可
2. **无 CLI 依赖**：不依赖 `claude` CLI，直接通过 hermes-agent 工具调用 API
3. **纯文本压缩**：代码块、URL、路径不会被压缩（规则保证）
4. **Hermes Agent 上下文**：压缩时保留 hermes-agent 特有的上下文标记（如 `[SILENT]`, `❯` 等）

### caveman 生态参考

| 项目 | Claude Code 用途 | Hermes Agent 对应 |
|---|---|---|
| `caveman` (grammar) | 输出压缩 | ✅ 直接采用 |
| `caveman-compress` (scripts) | 输入文件压缩 | ✅ 通过 MiniMax API |
| `cavemem` (memory) | 跨会话记忆 | ⚠️ 需适配 |
| `caveload` (restore) | 解压恢复 | ⚠️ 可选 |
| `CLAUDE.md` 集成 | 项目上下文压缩 | ✅ `~/.hermes/hermes-agent/CLAUDE.md` |
| cron 触发 | 定时压缩 | ⚠️ 可通过 cron script 集成 |
| hook 集成 | 自动压缩触发 | ⚠️ hermes-agent 无 hook 系统 |

## 压缩效果演示

### 英文压缩

| 原始 | Lite | Full | Ultra |
|---|---|---|---|
| I would like to request that you implement this feature as soon as possible | This implements this feature. | implements this feature ASAP. | impl this feature ASAP. |
| I think that we should probably consider using a cache for this | Consider using a cache. | Consider cache. | consider cache. |
| This is a test message that demonstrates the compression effect | This is a test message demonstrating compression. | test msg demonstrates compression. | test msg demonstrates compression effect. |
| In order to proceed with the installation, you will need to run the following command | To proceed with installation, run this command. | To install, run: | to install, run cmd. |
| The most important thing to consider here is that we need to be careful | Most important: be careful. | Important: be careful. | important: be careful. |
| Basically, what I want to say is that the implementation is working correctly | Implementation works correctly. | impl works. | impl works. |

### 中文压缩

| 原始 | 压缩 |
|---|---|
| 我想要请你帮我实现这个功能，最好能尽快完成 | 帮我 impl 这个功能 ASAP |
| 这个功能需要我们仔细考虑之后才能决定要不要做 | 需要仔细考虑后决定 |
| 好的，我现在来帮你分析和解决这个问题 | 来帮你分析和解决 |
| 让我先看一下这个问题是什么情况 | 看下问题 |
| 这个文件非常重要，因为它包含了所有重要的配置信息 | 文件重要，包含配置信息 |
| 如果你不明白的话，我可以再详细解释一下 | 不明白可再解释 |

### Token 节省估算

基于 caveman 官方测试（100 样本）：
- 平均压缩率：72.6%（英文）/ 68.3%（中文）
- 对于 1000 token 的响应，压缩后约 270-310 token
- 节省约 70% 的输出 token
- 输入文件（CLAUDE.md）从 ~5000 tokens 压缩到 ~1400 tokens

### 实际文件压缩案例

bash
# 压缩前
$ wc -c CLAUDE.md
20000 bytes (约 5000 tokens)

# 压缩后
$ cat CLAUDE.md | python3 compress_llm.py
# 输出约 5400 bytes (约 1350 tokens)
# 节省约 73% tokens


