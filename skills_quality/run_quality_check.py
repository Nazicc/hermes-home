#!/usr/bin/env python3
"""Run skills quality check and generate report."""

import sys
import os

# The skills_quality package is at /Users/can/.hermes/skills_quality/
# We need to add its PARENT to sys.path so "import skills_quality" works
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)  # /Users/can/.hermes/
sys.path.insert(0, PARENT_DIR)

os.environ.setdefault("HERMES_SKILLS_DIR", os.path.expanduser("~/.hermes/skills"))

from skills_quality.core import (
    SkillParser,
    PedagogicScorer,
    TriggerValidator,
    QualityReport,
    validate_structure,
    classify_skill_type,
)

SKILLS_DIR = os.environ["HERMES_SKILLS_DIR"]

def step1_find_stubs():
    """Step 1: List all stub skills (score <= 3)."""
    print("=" * 72)
    print("STEP 1: FIND ALL STUB SKILLS (score ≤ 3)")
    print("=" * 72)
    report = QualityReport(skills_dir=SKILLS_DIR)
    result = report.generate(tier="stub", sort="score", limit=50)
    if not result.skills:
        print("✅ No stub skills found!")
        return []
    print(f"🚨 Stub Skills ({len(result.skills)} found — need major work):\n")
    for i, s in enumerate(result.skills, 1):
        print(f"  {i}. {s['name']} ({s['line_count']} lines, {s['pedagogic_score']}/10)")
    print()
    return result.skills

def step3_get_suggestions(skill_names):
    """Step 3: Get improvement suggestions for selected stubs."""
    print("=" * 72)
    print("STEP 3: IMPROVEMENT SUGGESTIONS FOR LOWEST-SCORING STUBS")
    print("=" * 72)
    
    parser = SkillParser(skills_dir=SKILLS_DIR)
    scorer = PedagogicScorer()
    
    for name in skill_names:
        print(f"\n{'─' * 72}")
        skill = parser.parse_skill_by_name(name)
        if not skill:
            print(f"❌ Skill '{name}' not found.")
            continue
        
        score = scorer.score(skill)
        current = score.total
        target = 7
        
        print(f"💡 Improvement Path: {name}")
        print(f"   Current State: {score.tier.capitalize()} ({current}/10)")
        print(f"   Target: Good (7/10 minimum)")
        print(f"   GAP: +{target - current} points needed")
        print()

        gaps = []
        if score.teaching < 2:
            gaps.append(f"  ❌ Teaching (Why This Works): {score.teaching}→2 — Add a dedicated section explaining *why* this approach works")
        if score.anti_patterns < 2:
            gaps.append(f"  ❌ Anti-Patterns: {score.anti_patterns}→2 — Add 3+ named failure modes (e.g., **Feature Factory**, **Gold Plating**)")
        if score.examples < 2:
            gaps.append(f"  ❌ Examples: {score.examples}→2 — Add 2-3 concrete examples (good/bad/edge cases)")
        if score.when_not_to_use < 2:
            gaps.append(f"  ⚠️  When NOT to Use: {score.when_not_to_use}→2 — Add explicit boundary conditions")
        if score.cross_references < 2:
            gaps.append(f"  ⚠️  Cross-References: {score.cross_references}→2 — Link 3+ related skills")

        if gaps:
            print("   Gap Analysis:")
            for g in gaps:
                print(f"     {g}")
        
        print()
        print("   Priority Order:")
        print("     1. Add ## Purpose section (quickest win, +1-2 pts)")
        print("     2. Add ## Anti-Patterns with 3 named failure modes (+1-2 pts)")
        print("     3. Add 2 examples with real-world traces (+1 pt)")
        print("     4. Add ## When NOT to Use boundary (+1 pt)")
        print("     5. Add ## References linking related skills (+1 pt)")

        estimated_lines = 0
        if score.teaching < 2:
            estimated_lines += 30
        if score.anti_patterns < 2:
            estimated_lines += 40
        if score.examples < 2:
            estimated_lines += 50
        if score.when_not_to_use < 2:
            estimated_lines += 15
        if score.cross_references < 2:
            estimated_lines += 10

        if estimated_lines:
            print(f"\n   Estimated: ~{estimated_lines} lines to reach Good (7/10)")
        print(f"{'─' * 72}")

def step4_summary():
    """Step 4: Generate full quality distribution summary."""
    print("=" * 72)
    print("STEP 4: FULL QUALITY DISTRIBUTION SUMMARY")
    print("=" * 72)
    report = QualityReport(skills_dir=SKILLS_DIR)
    result = report.generate(tier="all", sort="score", limit=100)
    summary = result.summary
    
    tier_emoji = {"stub": "🗼", "developing": "📈", "good": "✅", "excellent": "⭐"}
    tier_map = {"stub": summary["stubs"], "developing": summary["developing"], 
                "good": summary["good"], "excellent": summary["excellent"]}
    
    total = summary['total_skills'] or 1
    
    print(f"\n📋 Hermes Skills Quality Report")
    print(f"   Total: {summary['total_skills']} skills")
    print()
    
    for tier_name in ["stub", "developing", "good", "excellent"]:
        count = tier_map.get(tier_name, 0)
        pct = count / total * 100
        bar_len = int(pct / 5)
        emoji = tier_emoji.get(tier_name, "?")
        print(f"   {emoji} {tier_name.capitalize():12s}: {count:3d} skills  {'█' * bar_len}{'░' * (20 - bar_len)} {pct:.1f}%")
    
    print(f"\n   Top skills by score:")
    for i, s in enumerate(result.skills[:10], 1):
        tier_char = {"stub": "🗼", "developing": "📈", "good": "✅", "excellent": "⭐"}.get(s["type"], "?")
        errors = len(s.get("errors", []))
        error_marker = f" ⚠️{errors}" if errors else ""
        print(f"     {i}. {tier_char} {s['name']}: {s['pedagogic_score']}/10{error_marker}")
    
    if summary.get("broken_references"):
        print(f"\n   ⚠️  {len(summary['broken_references'])} broken references detected")
    if summary.get("circular_references"):
        print(f"   🔄  {len(summary['circular_references'])} circular reference(s)")
    
    # Also list all skills with their scores for the complete picture
    print(f"\n   {'─' * 60}")
    print(f"   ALL SKILLS (sorted by score):")
    print(f"   {'─' * 60}")
    for i, s in enumerate(result.skills, 1):
        tier_char = {"stub": "🗼", "developing": "📈", "good": "✅", "excellent": "⭐"}.get(s["type"], "?")
        print(f"     {i:3d}. {tier_char} {s['name']:45s} {s['pedagogic_score']:2d}/10 ({s['line_count']:4d} lines)")

if __name__ == "__main__":
    # Step 1: Find stubs
    stubs = step1_find_stubs()
    
    if stubs:
        # Step 2: Skip detailed info (per instructions)
        
        # Step 3: Pick 2-3 lowest scoring stubs and get suggestions
        worst_stubs = sorted(stubs, key=lambda s: s['pedagogic_score'])[:3]
        worst_names = [s['name'] for s in worst_stubs]
        step3_get_suggestions(worst_names)
    
    # Step 4: Full summary
    print()
    step4_summary()
