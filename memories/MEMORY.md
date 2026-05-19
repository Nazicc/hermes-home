## 📁 MEMORY — Hermes Agent Persistent Memory
## 格式：每条记忆以 § 分隔；[标签] 标注分类；末尾注过期时间

══════════════════════════════════════════════
## 🖥️ 环境配置 [ENV] · 2026-04-19
══════════════════════════════════════════════
§
[ENV · 永久] 工作目录：/Users/can/.hermes/hermes-agent（所有文件读写只能在此）
§
[ENV · 永久] 主力Provider: Volcengine/GLM-5.1；MiniMax CLI已认证可用(120 img/周)，命令: mmx image generate "prompt" -o out.png
§
§
[USER · 永久] 用户名：r00tcc（飞书平台）
§
[USER · 永久] 沟通偏好：中文；简洁直接；不喜欢废话
§
[USER · 永久] 每天结束前必须 commit 所有改动，不留任何遗留工作。
§
[USER · 永久] 工作风格：分析后立即 full implementation；完整流程：分析→测试→安装→回归测试→上线；偏好系统性落地；每天结束前 commit
§
[SECURITY · 2026-04-29] git 仓库敏感信息审计：先用 `git log origin/main..HEAD` 扫 unpushed commits；用 `git log --all -S "sk-" --oneline` 搜历史（比 grep 快）；`.gitignore` 确保 `evolver/` 等含真实 key 的 .env 目录被排除；测试文件中的 `ghp_xx...xxxx` 类是占位符，非泄露；skills-quality 会误判 git 读取命令为 dangerous，skill 创建会被 block
§
[ENV · 2026-05-01] skills/ gitlink→普通目录已修复；push 408网络问题；skills/新增3个security skill(Hack-with-Github/Awesome-Hacking)
§
[ENV · 2026-05-19] OpenViking 已修复：端口1933，挂载 ~/.openviking:/app/.openviking，嵌入 = 硅基流动 BAAI/bge-large-zh-v1.5。所有 Viking 工具(viking_search/read/browse/remember/add_resource/memory_recall) 正常工作。FAL_KEY 在 .env 但未被启用（image_generate 用 MiniMax CLI）
§
[MULTI-AGENT · 2026-05-12] Hermes v2 方案已写：`/Users/can/.hermes/docs/multi-agent-team-v2.md`（18,614字节）。核心：4层体系(L0 Lead/L1 Profile/L2 delegate_task/L3 cron)；Hermes官方机制+Claude Code Agent Teams 5理念融合。Profile=一等公民(独立SOUL.md/.env/state.db/gateway)；Honcho共享记忆；Beads任务板；邮箱协议；Git worktree隔离。
§
BLOOM方法论已内化：用户要求我所有复杂任务必须按B→L→O→O→M五步执行（Background身份设定→Location目标限定→Obligation约束规则→Output格式规范→Modify迭代优化），禁止跳过、禁止通用浅层回答。
§
[ENV · 永久] CodeGraph MCP 工具默认禁用（disabled_toolsets: [mcp-codegraph]），需要时 /tools enable mcp-codegraph 启用，用完 /tools disable mcp-codegraph 关掉。避免每轮 6KB Schema 的 token 浪费。
§
[ENV · 2026-05-18] 上下文配置优化：max_turns=40, compression.threshold=0.40, protect_last_n=8, hygiene_hard_message_limit=100。废弃的 evolver/ 目录已删除。
§
[ENV · 2026-05-19] 每日4-6点自学cron已设置(self-evolution-learning, 轮换CMA研究方向)。Excalidraw→PNG: Playwright headless Chromium + 分享URL + screenshot。