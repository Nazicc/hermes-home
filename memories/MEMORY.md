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
[USER · 永久] 用户 r00tcc（飞书）。中文简洁偏好。工作风格：分析→全实现→测试→安装→回归→上线。每天末commit。Git重建：orphan清远程→empty commit→force push。
§
[ENV] TDB-AM: Docker :8420, plugin ~/.hermes/hermes-agent/plugins/memory/memory_tencentdb/, config provider=memory_tencentdb
§
BLOOM方法论已内化：用户要求我所有复杂任务必须按B→L→O→O→M五步执行（Background身份设定→Location目标限定→Obligation约束规则→Output格式规范→Modify迭代优化），禁止跳过、禁止通用浅层回答。
§
[FEATURE · 2026-05-24] 飞书输出偏好：紧凑键值列表（▸项✅摘要），禁 Markdown 表格。
§
[FRAMEWORK · 永久] Hermes+Obsidian 联动框架：Hermes=AI调度中枢(模型/技能编排/任务执行)，Obsidian=本地存储仓库(笔记/素材/双链知识)。5大核心联动：智能检索/双向读写/专属技能/自动化工作流/格式适配。5大场景：知识管理/内容创作/逻辑推理/项目办公/智能体训练。规则：区分职能边界→管控权限→适配双链Markdown→小规模测试→定期备份→按需搭建技能流。已有obsidian/obsidian-canvas-creator/mermaid-visualizer/sn-md-to-html-report/sn-ppt等技能可用。
§
[FIXED · 2026-05-25] SimpleMem Bridge: get_last_ended_at() float(content.split('\n')[0])修复；MAX_SESSIONS_PER_RUN=5限制防止积压；cron正常。ECCES: AgentShield v1.5.0扫Hermes Grade C/60,15+语言安全规则提取,ecc-security-toolkit技能已创建
§
[LEARNED · 2026-05-24] Feishu Gateway 崩溃修复——用户通过 nanobot 修复 Hermes Feishu Gateway 的方法有效。Gateway 在 launchd 中的症状：state = spawn scheduled + last exit code = 1。修复后 gateway 在 port 8642 正常 LISTEN，飞书消息可正常收发。
§
[FRAMEWORK · 2026-05-25] AI个人重大决策辅助系统已内化。核心：AI做分析推演，用户做最终决定。5模块：①个人基准档案（诉求/资源/底线/目标）②客观信息搜集（案例/行业/多方利弊）③多维量化分析（成本/收益/长短期）④多方案路径推演（备选方案+乐观/中性/悲观模拟）⑤风险兜底预案（隐患+止损+退路）。五步流程：明确问题→录入现状→AI分析输出方案→模拟评估→用户定夺。应用场景：职业/财富/生活/副业。必须附带风险提示，增加反向质疑视角，拉长时间维度输出。
§
[PERMANENT · 2026-05-26] 决策案例库持久化路径：/Users/can/.hermes/hermes-agent/decisions/，每个 .md 文件记录一次决策分析，INDEX.md 自动维护索引。ai-decision-assistant skill 每次启用后必须将报告写入 decisions/ 目录。
§
[FRAMEWORK · 2026-05-25] Skills Bundles（技能包）体系已内化：将多个独立基础技能按场景/流程/逻辑打包，解决单技能孤立执行、操作繁琐、数据不通问题。核心：子技能集合+流程规则+数据规则+管控容错。搭建流程：拆解需求→拆分任务→编排依赖→统一参数→配置容错→联调测试→归档上线。agent规则：多步骤固定流程优先用技能包；强依赖步骤禁止跳步；统一参数格式+全局上下文；异常兜底必配；控制包体量剔除冗余；整体权限管理+归档。