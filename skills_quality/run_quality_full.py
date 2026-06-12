#!/usr/bin/env python3
"""Get full skills quality report with all skills."""

import sys, os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)
os.environ.setdefault("HERMES_SKILLS_DIR", os.path.expanduser("~/.hermes/skills"))

from skills_quality.core import QualityReport

SKILLS_DIR = os.environ["HERMES_SKILLS_DIR"]
report = QualityReport(skills_dir=SKILLS_DIR)
result = report.generate(tier="all", sort="score", limit=200)

summary = result.summary
tier_emoji = {"stub": "🗼", "developing": "📈", "good": "✅", "excellent": "⭐"}

total = summary['total_skills'] or 1
for tier_name in ["stub", "developing", "good", "excellent"]:
    count = summary.get(tier_name, 0)
    pct = count / total * 100
    bar_len = int(pct / 5)
    emoji = tier_emoji.get(tier_name, "?")
    print(f"{emoji} {tier_name.capitalize():12s}: {count:3d} skills  {'█' * bar_len}{'░' * (20 - bar_len)} {pct:.1f}%")

print(f"\nTotal: {summary['total_skills']} skills")
print(f"Broken refs: {len(summary.get('broken_references', []))}")
print(f"Circular refs: {len(summary.get('circular_references', []))}")
print()

# All skills sorted by score ascending (stubs first, then developing, then good/excellent)
print("ALL SKILLS (score ascending):")
print(f"{'#':>4s} {'Score':>5s} {'Tier':>11s} {'Lines':>5s}  Name")
print(f"{'─'*4} {'─'*5} {'─'*11} {'─'*5}  {'─'*40}")
for i, s in enumerate(result.skills, 1):
    tier_char = tier_emoji.get(s["type"], "?")
    print(f"{i:4d} {s['pedagogic_score']:5d}/10 {tier_char+' '+s['type']:>11s} {s['line_count']:5d}  {s['name']}")
