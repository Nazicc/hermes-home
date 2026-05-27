# 学习笔记 — 2026-05-28 04:00-06:00

## 主题
**Hermes Agent 自我进化系统深度调研** — 理解已部署的 self-evolution pipeline 现状、架构全貌、以及当前错误根因

---

## ▸ 检查项 状态 摘要

▸ **健康检查** ✅ 通过 — DEEPSEEK_API_KEY 就绪，LiteLLM + DSPy 3.2.0 加载正常，GEPA/MIPROv2 均可用
▸ **待进化 skill 选择** ✅ 完成 — mcporter（8,466→822 chars, +10.3%）已成功部署
▸ **whisper skill 进化** ❌ 失败 — 同一批次运行失败（错误信息被截断）
▸ **11 个 skill 已完成进化** ✅ — mcporter/memory-optimizer/cron-job-error-recovery 等
▸ **evolution-health-check cron** ❌ 错误 — `cannot import name 'ToolResult' from 'agent'` (13次失败)
▸ **skills-quality-review cron** ✅ 最近运行 04:04:18 成功

---

## 一、当前运行的自我进化 cron jobs（jobs.json 分析）

共 10 个活跃 cron job，其中 3 个与进化直接相关：

| Job ID | 名称 | 调度 | 状态 | 最近错误 |
|--------|------|------|------|---------|
| a6dca85ab7a8 | evolver-bridge | 每 30m | ok | — |
| 5d27c1221c4b | evolution-health-check | 10:00 | **error** | ToolResult 导入失败 |
| 8a91ef5593a1 | self-evolution-cycle | 02:00 | **error** | whisper 进化失败 |

**关键发现**：`self-evolution-cycle` (02:00) 是核心进化 job，5 月 28 日运行结果：
- mcporter ✅ 基准分 0.484 → 进化后 0.534（+10.3%），体积累计压缩 86%（8,466→822 chars）
- whisper ❌ 失败（错误信息被截断）

---

## 二、Evolver 架构全貌（hermes-agent-self-evolution）

```
hermes-agent-self-evolution/
├── evolution/
│   ├── core/          # 核心基础设施
│   │   ├── config.py          # EvolutionConfig 配置
│   │   ├── constraints.py     # 约束验证器（size/growth/non_empty/skill_structure）
│   │   ├── dataset_builder.py # 评估数据集生成（synthetic/sessionDB/golden）
│   │   ├── fitness.py         # LLM-as-judge 评分（FitnessScore 4维度）
│   │   └── external_importers.py
│   ├── skills/        # Phase 1：Skill 进化（已实现）
│   │   ├── evolve_skill.py    # 主入口，GEPA 优化循环
│   │   └── skill_module.py    # SKILL.md → DSPy Module 包装器
│   ├── tools/         # Phase 2：Tool description 进化（未实现）
│   ├── prompts/       # Phase 3：System prompt 进化（未实现）
│   ├── code/          # Phase 4：Code 进化（未实现）
│   └── monitor/       # Phase 5：持续循环（空目录）
├── datasets/          # 生成的评估数据集
├── output/            # 进化输出（11 个 skill 已进化）
│   ├── mcporter/20260528_020601/
│   │   ├── baseline_skill.md (8,968 chars)
│   │   ├── evolved_skill.md (1,164 chars) ← 已部署
│   │   └── metrics.json
│   └── ...（10 个其他 skill）
└── reports/            # 存档报告（phase1_validation_report.pdf）
```

---

## 三、SkillModule — 核心 DSPy 包装机制

`skill_module.py`（131 行）实现了 SKILL.md → DSPy Module 的关键转换：

```python
# 关键函数
load_skill(skill_path)     # 解析 YAML frontmatter + body
find_skill(skill_name)      # os.walk 遍历（跟随 symlink）
reassemble_skill(raw)      # 保留 frontmatter，重写 body

# DSPy Signature
class SkillModule(dspy.Module):
    # InputField: skill_instructions (str), task_input (str)
    # OutputField: output (str)
    # 内置 dspy.ReAct 推理
```

**GEPA（Genetic Evolution via Prompt Adjustment）** 是主要优化器：
- 使用 reflective analysis（分析执行轨迹理解失败原因）
- 只需 3 个样本即可工作
- 在 10 个样本上训练，5 个验证，5 个 holdout
- 对体积累计压缩效果显著（mcporter: -86%）

---

## 四、Fitness & Constraints 机制

**FitnessScore**（fitness.py）：4 维度评分 → composite score
- correctness 50% + procedure_following 30% + conciseness 20% - length_penalty

**ConstraintValidator**（constraints.py）：硬约束，全部通过才接受
1. size_limit（artifact_type 相关）
2. growth_limit（相比 baseline 的增长上限）
3. non_empty（不能为空）
4. skill_structure（YAML frontmatter 完整性）

---

## 五、当前错误分析

### Error 1: evolution-health-check — ToolResult 导入失败
```
cannot import name 'ToolResult' from 'agent' (/Users/can/.hermes/hermes-agent/agent/__init__.py)
```

**根本原因**：cron job 在 `hermes-agent` venv Python (`/Users/can/.hermes/hermes-agent/venv/bin/python`) 下执行，而 `hermes-agent-self-evolution` 也有自己的 venv (`hermes-agent-self-evolution-venv`)。两者的 `agent/` 模块路径不同：
- `hermes-agent` venv 中 `agent/` 作为已安装包存在，可以正常 `from agent import ToolResult`
- evolver 的 Python 环境中没有 `agent/` 模块

检查 evolution-self-check.sh 使用的 VENV_PYTHON：
```bash
VENV_PYTHON="/Users/can/.hermes/hermes-agent-self-evolution-venv/bin/python"
```
✅ 正确使用的是 evolver 的 venv

但问题可能是 evolution-health-check job 的 prompt 调用了 hermes-agent 自身的 agent 模块（在 hermes-agent venv 下），而 evolver self-check 脚本本身（作为 bash 脚本）没有问题。错误信息 `ToolResult` 来自某个 Python 路径冲突。

### Error 2: whisper 进化失败
→ 从 jobs.json 中看到 `last_error: "RuntimeError: ## Hermes Agent 自进化..."`，但错误信息被截断
→ 需要查看完整错误日志，位置：`~/.hermes/cron/output/8a91ef5593a1/`

### 路径问题：evolver_to_simplemem 找不到 events.jsonl
```
WARNING: /Users/can/.hermes/hermes-agent/hermes-agent-self-evolution/assets/gep/events.jsonl not found
```
hermes_to_evolver_bridge.py (Step 1) 应该生成 events.jsonl 到 `hermes-agent-self-evolution/assets/gep/`，但 Step 2 在查找时路径可能不存在。
检查发现：evolver-bridge cron job 每次运行都跳过了 53 个事件（checkpoint），说明事件文件路径有误或 Step 1 根本没有运行。

---

## 六、11 个已进化 skill 一览

| Skill | 最近运行 | 迭代 |
|-------|---------|------|
| mcporter | 2026-05-28 02:06 | 5 |
| memory-optimizer | 2026-05-27 02:09 | — |
| cron-job-error-recovery | 2026-05-27 02:05 | — |
| hermes-self-evolution-pipeline | 2026-05-26 02:11 | — |
| eval-suite | 2026-05-26 02:09 | — |
| context-engineering | 2026-05-19 | — |
| ... | — | — |

**注意**：output/ 目录只有目录结构，没有实际的 metrics.json 文件 → 这说明很多进化可能是 dry-run 或未完成

---

## 关键发现

1. **Phase 1（Skill 进化）是唯一运行的阶段**，tools/prompts/code/monitor 都是空目录
2. **GEPA 优化效果显著** — mcporter 体征压缩 86%，分数提升 10.3%
3. **约束驱动压缩** — 约束验证器（growth_limit）强制体征收缩，避免膨胀
4. **DSPy 3.2.0 就绪** — GEPA 和 MIPROv2 都可用
5. **有可参考的完整运行记录** — mcporter 有完整的 metrics.json

---

## 下一步

1. **修复 evolution-health-check 错误** — 检查 `agent/__init__.py` 的 ToolResult 导入问题
2. **调查 whisper 失败原因** — 查看完整错误日志
3. **验证 mcporter 进化结果是否已部署** — metrics.json 显示已部署到 skills/mcp/mcporter/SKILL.md
4. **探索 Phase 2-5 基础设施** — tools/prompts/code 目录是否已有代码框架
5. **检查 evolution-skills 的 dataset_builder** — 理解 synthetic 数据生成逻辑

---

*笔记生成时间：2026-05-28 04:30 北京时间*