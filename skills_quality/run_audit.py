#!/usr/bin/env python3
"""Run a comprehensive skills quality audit - stubs, lowest 5, and developing skills with potential."""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills_quality.core import (
    SkillParser, PedagogicScorer, DependencyGraph, TriggerValidator,
    QualityReport, validate_structure, classify_skill_type,
    extract_references, validate_references,
    PedagogicScore, ReportResult,
)

SKILLS_DIR = os.environ.get("HERMES_SKILLS_DIR", str(Path.home() / ".hermes" / "skills"))

# Step 1: Find all stubs (score <= 3)
print("=" * 60)
print("STEP 1: STUB SKILLS STATISTICS")
print("=" * 60)
report = QualityReport(skills_dir=SKILLS_DIR)
result = report.generate(tier="stub", sort="score", limit=200)
summary = result.summary
print(f"Total skills: {summary['total_skills']}")
print(f"Stub skills (score ≤ 3): {summary['stubs']}")
print(f"Developing skills (4-6): {summary['developing']}")
print(f"Good skills (7-8): {summary['good']}")
print(f"Excellent skills (9-10): {summary['excellent']}")

# Step 2: Lowest 5 skills with improvement suggestions
print()
print("=" * 60)
print("STEP 2: LOWEST 5 SKILLS BY SCORE")
print("=" * 60)

lowest_result = report.generate(tier="all", sort="score", limit=200)
# Sort by score ascending
sorted_skills = sorted(lowest_result.skills, key=lambda s: s["pedagogic_score"])
bottom5 = sorted_skills[:5]

parser = SkillParser(skills_dir=SKILLS_DIR)
scorer = PedagogicScorer()

for s in bottom5:
    name = s["name"]
    print(f"\n--- #{s['pedagogic_score']}/10: {name} ---")
    skill = parser.parse_skill_by_name(name)
    if skill:
        score = scorer.score(skill)
        gaps = []
        if score.teaching < 2:
            gaps.append(f"Teaching: {score.teaching}/2")
        if score.anti_patterns < 2:
            gaps.append(f"Anti-Patterns: {score.anti_patterns}/2")
        if score.examples < 2:
            gaps.append(f"Examples: {score.examples}/2")
        if score.when_not_to_use < 2:
            gaps.append(f"When NOT to Use: {score.when_not_to_use}/2")
        if score.cross_references < 2:
            gaps.append(f"Cross-References: {score.cross_references}/2")
        print(f"  Line count: {skill.line_count}")
        print(f"  Gaps: {', '.join(gaps)}")
        desc = skill.description or "(no description)"
        if len(desc) > 80:
            desc = desc[:77] + "..."
        print(f"  Description: {desc}")

# Step 3: Highest developing skills (closest to "good")
print()
print("=" * 60)
print("STEP 3: TOP 5 DEVELOPING SKILLS (closest to Good)")
print("=" * 60)

developing_result = report.generate(tier="developing", sort="score", limit=200)
# Sort by score descending (highest developing first)
dev_sorted = sorted(developing_result.skills, key=lambda s: s["pedagogic_score"], reverse=True)
top5_dev = dev_sorted[:5]

for s in top5_dev:
    name = s["name"]
    print(f"\n--- #{s['pedagogic_score']}/10: {name} ---")
    skill = parser.parse_skill_by_name(name)
    if skill:
        score = scorer.score(skill)
        missing = round(7 - score.total)
        gaps = []
        if score.teaching < 2:
            gaps.append(f"Teaching: {score.teaching}→2")
        if score.anti_patterns < 2:
            gaps.append(f"Anti-Patterns: {score.anti_patterns}→2")
        if score.examples < 2:
            gaps.append(f"Examples: {score.examples}→2")
        if score.when_not_to_use < 2:
            gaps.append(f"When NOT: {score.when_not_to_use}→2")
        if score.cross_references < 2:
            gaps.append(f"Refs: {score.cross_references}→2")
        print(f"  Line count: {skill.line_count}")
        print(f"  Missing {missing} pts to Good (7/10)")
        print(f"  Gaps: {', '.join(gaps)}")
        desc = skill.description or "(no description)"
        if len(desc) > 80:
            desc = desc[:77] + "..."
        print(f"  Description: {desc}")

# Step 4: Summary statistics
print()
print("=" * 60)
print("STEP 4: SUMMARY & RECOMMENDATIONS")
print("=" * 60)

print(f"\nTotal skills: {summary['total_skills']}")
print(f"  🗼 Stubs (0-3):  {summary['stubs']}  — need major rewrite or removal")
print(f"  📈 Developing (4-6): {summary['developing']}  — can upgrade to Good")
print(f"  ✅ Good (7-8):    {summary['good']}  — meets PM standard")
print(f"  ⭐ Excellent (9-10): {summary['excellent']}  — model quality")

print(f"\nLowest 5 skills (core defects):")
for s in bottom5:
    print(f"  🗼 {s['name']}: {s['pedagogic_score']}/10 ({s['line_count']} lines)")

print(f"\nTop 5 developing skills with upgrade potential:")
for s in top5_dev:
    print(f"  📈 {s['name']}: {s['pedagogic_score']}/10 — +{7 - s['pedagogic_score']} pts to Good")

print(f"\nRecommended priority actions (max 5):")
print(f"  1. {bottom5[0]['name']}: add Purpose + Anti-Patterns + Examples (quickest wins)")
print(f"  2. {bottom5[1]['name']}: same — these are stubs with <5 lines, need full rewrite")
print(f"  3. {top5_dev[0]['name']}: add {7 - top5_dev[0]['pedagogic_score']} pts — closest to Good, highest ROI")
print(f"  4. {top5_dev[1]['name']}: add {7 - top5_dev[1]['pedagogic_score']} pts — second closest to Good")
print(f"  5. Overall: focus on developing tier first (+{summary['developing']} skills) — each needs 1-3 pts")
