#!/usr/bin/env python3
"""Final quality audit report - produces structured output."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from skills_quality.core import QualityReport, PedagogicScorer, SkillParser

SKILLS_DIR = str(Path.home() / ".hermes" / "skills")
report = QualityReport(skills_dir=SKILLS_DIR)
parser = SkillParser(skills_dir=SKILLS_DIR)
scorer = PedagogicScorer()

# Get full report, deduplicate names (keep highest score)
full = report.generate(tier='all', sort='score', limit=500)
all_skills = full.skills

seen = {}
for s in all_skills:
    name = s['name']
    score = int(s['pedagogic_score'])
    if name not in seen or score > int(seen[name]['pedagogic_score']):
        seen[name] = s

deduped = list(seen.values())

# Count tiers
d_stubs = [s for s in deduped if int(s['pedagogic_score']) <= 3]
d_dev = [s for s in deduped if 4 <= int(s['pedagogic_score']) <= 6]
d_good = [s for s in deduped if 7 <= int(s['pedagogic_score']) <= 8]
d_exc = [s for s in deduped if int(s['pedagogic_score']) >= 9]

# Lowest 5
sorted_all = sorted(deduped, key=lambda x: int(x['pedagogic_score']))
bottom5 = sorted_all[:5]

# Top 5 developing
sorted_dev = sorted(d_dev, key=lambda x: int(x['pedagogic_score']), reverse=True)
top5_dev = sorted_dev[:5]

# Check duplicates dir
dup_dir = Path(SKILLS_DIR) / 'skills'
dup_count = len(list(dup_dir.iterdir())) if dup_dir.exists() else 0

# ====== OUTPUT ======
print("=" * 60)
print("Hermes Skills 质量审查报告")
print("=" * 60)

print(f"\n>> 总体统计 (去重后 {len(deduped)} 个唯一技能)")
print(f"  真实 SKILL.md 文件总数: {len(list(Path(SKILLS_DIR).rglob('SKILL.md')))}")
print(f"  去重后唯一技能数:       {len(deduped)}")
print(f"  Stub (0-3):              {len(d_stubs)}  ({len(d_stubs)/max(len(deduped),1)*100:.1f}%)")
print(f"  Developing (4-6):        {len(d_dev)}  ({len(d_dev)/max(len(deduped),1)*100:.1f}%)")
print(f"  Good (7-8):              {len(d_good)}  ({len(d_good)/max(len(deduped),1)*100:.1f}%)")
print(f"  Excellent (9-10):        {len(d_exc)}  ({len(d_exc)/max(len(deduped),1)*100:.1f}%)")
print(f"  Good+ 通过率: {(len(d_good)+len(d_exc))/max(len(deduped),1)*100:.1f}%")

# Detect duplicate skill directory bug
if dup_count > 10:
    print(f"\n  !! 严重问题: skills/skills/ 目录有 {dup_count} 个子目录, 导致重复计分")
    print(f"     7 个技能因重复 stub 版本被评 0/10 (claude-code, jupyter-live-kernel, linear 等)")

print(f"\n" + "-" * 60)
print("STEP 1: 最低分 5 个技能 -- 核心缺陷")
print("-" * 60)

for s in bottom5:
    name = s['name']
    score = int(s['pedagogic_score'])
    skill = parser.parse_skill_by_name(name)
    if not skill:
        print(f"\n  {name}: {score}/10 -- 无法解析")
        continue
    sc = scorer.score(skill)
    sections = list(skill.sections.keys())
    desc = (skill.description or "(无描述)")[:60]

    print(f"\n  [{name}] {score}/10  ({skill.line_count} 行)")
    print(f"  描述: {desc}")
    print(f"  Sections: {sections}")
    print(f"  分项得分: T={sc.teaching}/2 AP={sc.anti_patterns}/2 Ex={sc.examples}/2 WNU={sc.when_not_to_use}/2 XR={sc.cross_references}/2")

    gaps = []
    if sc.teaching < 2: gaps.append(f"+{2-sc.teaching} (Teaching)")
    if sc.anti_patterns < 2: gaps.append(f"+{2-sc.anti_patterns} (Anti-Patterns)")
    if sc.examples < 2: gaps.append(f"+{2-sc.examples} (Examples)")
    if sc.when_not_to_use < 2: gaps.append(f"+{2-sc.when_not_to_use} (WhenNOT)")
    if sc.cross_references < 2: gaps.append(f"+{2-sc.cross_references} (XRefs)")
    print(f"  需补充: {', '.join(gaps)}")

print(f"\n" + "-" * 60)
print("STEP 2: 最有升级潜力的 5 个 Developing 技能")
print("-" * 60)

for s in top5_dev:
    name = s['name']
    score = int(s['pedagogic_score'])
    skill = parser.parse_skill_by_name(name)
    if not skill:
        print(f"\n  {name}: {score}/10 -- 无法解析")
        continue
    sc = scorer.score(skill)
    missing = max(0, 7 - score)
    desc = (skill.description or "(无描述)")[:60]

    print(f"\n  [{name}] {score}/10  ({skill.line_count} 行) -- 距 Good 差 {missing} 分")
    print(f"  描述: {desc}")
    print(f"  分项得分: T={sc.teaching}/2 AP={sc.anti_patterns}/2 Ex={sc.examples}/2 WNU={sc.when_not_to_use}/2 XR={sc.cross_references}/2")

    wins = []
    if sc.teaching < 2: wins.append(f"Why This Works (+{2-sc.teaching})")
    if sc.anti_patterns < 2: wins.append(f"Anti-Patterns (+{2-sc.anti_patterns})")
    if sc.examples < 2: wins.append(f"Examples (+{2-sc.examples})")
    if sc.when_not_to_use < 2: wins.append(f"When not to Use (+{2-sc.when_not_to_use})")
    if sc.cross_references < 2: wins.append(f"XRefs (+{2-sc.cross_references})")
    print(f"  快速升级: {'; '.join(wins)}")

print(f"\n" + "=" * 60)
print("STEP 3: 总结与改进行动")
print("=" * 60)

print(f"\n现状: {len(deduped)} 技能 | Stub={len(d_stubs)} Dev={len(d_dev)} Good={len(d_good)} Exc={len(d_exc)}")
print(f"Good+通过率: {(len(d_good)+len(d_exc))/max(len(deduped),1)*100:.1f}%  (目标: >=85%)")

print(f"\n最低分 5 技能:")
for s in bottom5:
    print(f"  {s['name']}: {s['pedagogic_score']}/10")

print(f"\nTop 5 Developing (最接近 Good):")
for s in top5_dev:
    print(f"  {s['name']}: {s['pedagogic_score']}/10 (+{7-int(s['pedagogic_score'])}分)")

print(f"\n=== 5 条优先级改进行动 ===")
print(f"")
print(f"  1. [清理] 删除 skills/skills/ 重复目录 ({dup_count} 个子目录)")
print(f"     立即消除 7 个伪 0/10 评分, 恢复真实数据")
print(f"")
print(f"  2. [高ROI] 升级 {len(d_dev)} 个 Developing 技能至 Good")
print(f"     每项距 Good 仅差 1-3 分, 是投入产出比最高的目标")
print(f"     重点: 统一补 Why This Works + Cross-References 两个维度")
print(f"")
print(f"  3. [最高ROI] {top5_dev[0]['name']} ({top5_dev[0]['pedagogic_score']}/10)")

skill = parser.parse_skill_by_name(top5_dev[0]['name'])
if skill:
    sc = scorer.score(skill)
    actions = []
    if sc.teaching < 2: actions.append(f"添加 Why This Works (+{2-sc.teaching}分, ~30行)")
    if sc.anti_patterns < 2: actions.append(f"添加 3+ named Anti-Patterns (+{2-sc.anti_patterns}分, ~40行)")
    if sc.examples < 2: actions.append(f"添加 2-3 个 Examples (+{2-sc.examples}分, ~50行)")
    if sc.when_not_to_use < 2: actions.append(f"添加 When NOT to Use (+{2-sc.when_not_to_use}分, ~15行)")
    if sc.cross_references < 2: actions.append(f"添加 Cross-References (+{2-sc.cross_references}分, ~10行)")
    for a in actions:
        print(f"     {a}")

print(f"")
print(f"  4. [次高ROI] {top5_dev[1]['name']} ({top5_dev[1]['pedagogic_score']}/10)")
skill2 = parser.parse_skill_by_name(top5_dev[1]['name'])
if skill2:
    sc2 = scorer.score(skill2)
    actions2 = []
    if sc2.cross_references < 2: actions2.append(f"添加 XRefs (+{2-sc2.cross_references}分)")
    if sc2.teaching < 2: actions2.append(f"添加 Teaching (+{2-sc2.teaching}分)")
    if sc2.when_not_to_use < 2: actions2.append(f"添加 WhenNot (+{2-sc2.when_not_to_use}分)")
    if sc2.anti_patterns < 2: actions2.append(f"添加 Anti-P (+{2-sc2.anti_patterns}分)")
    for a in actions2:
        print(f"     {a}")

print(f"")
print(f"  5. [填补空白] {bottom5[0]['name']}({bottom5[0]['pedagogic_score']}/10) 和 {bottom5[1]['name']}({bottom5[1]['pedagogic_score']}/10)")
if int(bottom5[0]['pedagogic_score']) <= 3:
    print(f"     需从零构建: Purpose -> Examples -> Anti-Patterns 基础三件套")
else:
    print(f"     需补: Teaching, Examples, XRefs 维度")
