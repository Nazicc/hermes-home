#!/usr/bin/env python3
"""Comprehensive skill quality review script."""
import json, os, re, pathlib, collections, math

SKILLS_DIR = os.path.expanduser("~/.hermes/skills")

# Load stats
stats_path = os.path.join(SKILLS_DIR, "skill_stats.json")
stats = {}
if os.path.exists(stats_path):
    with open(stats_path) as f:
        stats = json.load(f)

def find_all_skills():
    """Find all skills by locating SKILL.md files."""
    skills = []
    for root, dirs, files in os.walk(SKILLS_DIR):
        for f in files:
            if f == "SKILL.md":
                rel_path = os.path.relpath(root, SKILLS_DIR)
                skills.append({
                    "path": root,
                    "rel_path": rel_path,
                    "name": rel_path.replace("/", "-") if "/" in rel_path else rel_path,
                    "full_name": rel_path
                })
    return skills

def analyze_skill(skill):
    """Analyze a skill's SKILL.md and associated files."""
    spath = skill["path"]
    name = skill["name"]
    full_name = skill["full_name"]
    md_path = os.path.join(spath, "SKILL.md")
    
    result = {
        "name": name,
        "full_name": full_name,
        "score": 0,
        "md_size": 0,
        "md_lines": 0,
        "has_tests": False,
        "has_examples": False,
        "has_code": False,
        "has_readme": False,
        "has_config": False,
        "has_manifest": False,
        "has_dependencies": False,
        "has_instructions": False,
        "has_description": False,
        "code_file_count": 0,
        "file_count": 0,
        "all_files": [],
        "inject_count": 0,
        "effectiveness": 0.5,
        "issues": []
    }
    
    # Count files in skill dir
    try:
        all_files = []
        for f in os.listdir(spath):
            fp = os.path.join(spath, f)
            if os.path.isfile(fp):
                all_files.append(f)
        result["all_files"] = all_files
        result["file_count"] = len(all_files)
    except:
        pass
    
    # Parse SKILL.md
    md_content = ""
    try:
        with open(md_path) as f:
            md_content = f.read()
        result["md_size"] = len(md_content)
        result["md_lines"] = md_content.count("\n") + 1
    except:
        result["issues"].append("Cannot read SKILL.md")
        return result
    
    # Check content depth
    if result["md_size"] < 500:
        result["issues"].append("SKILL.md too short (<500 bytes)")
    elif result["md_size"] < 2000:
        result["issues"].append("SKILL.md minimal (<2KB)")
    
    # Check for sections
    sections_found = []
    section_patterns = [
        (r"##\s*(Description|Overview|Summary)", "description_section"),
        (r"##\s*(Usage|How to|Instructions|Workflow)", "usage_section"),
        (r"##\s*(Configuration|Setup|Prerequisites)", "config_section"),
        (r"##\s*(Examples|Demo|Sample)", "examples_section"),
        (r"##\s*(Notes|Tips|Best Practices|Caution)", "notes_section"),
        (r"##\s*(Dependencies|Requirements)", "deps_section"),
        (r"(test|example|sample)", "test_example_mention"),
    ]
    for pat, key in section_patterns:
        if re.search(pat, md_content, re.IGNORECASE):
            sections_found.append(key)
    
    result["sections"] = sections_found
    result["has_description"] = "description_section" in sections_found
    result["has_instructions"] = "usage_section" in sections_found
    result["has_config"] = "config_section" in sections_found
    result["has_examples"] = "examples_section" in sections_found
    result["has_dependencies"] = "deps_section" in sections_found
    
    # Check for code/test files
    code_exts = {'.py', '.js', '.ts', '.sh', '.rb', '.go', '.rs', '.java', '.mjs', '.cjs'}
    for f in all_files:
        ext = os.path.splitext(f)[1].lower()
        if ext in code_exts:
            result["code_file_count"] += 1
            result["has_code"] = True
        if 'test' in f.lower() or 'spec' in f.lower() or 'check' in f.lower():
            result["has_tests"] = True
    
    # Manifest
    if "manifest.json" in all_files:
        result["has_manifest"] = True
    
    # Stats from skill_stats.json
    stat_name = name
    if stat_name in stats:
        s = stats[stat_name]
        result["inject_count"] = s.get("inject_count", 0)
        result["effectiveness"] = s.get("effectiveness", 0.5)
    
    # Compute score (0-10)
    score = 5  # baseline
    
    # SKILL.md size contribution (up to +2)
    if result["md_size"] >= 5000:
        score += 2
    elif result["md_size"] >= 2000:
        score += 1
    elif result["md_size"] < 500:
        score -= 2
    
    # Section coverage (up to +1.5)
    section_score = min(len([s for s in sections_found if s != "test_example_mention"]) * 0.3, 1.5)
    score += section_score
    
    # Has code files (+0.5)
    if result["has_code"]:
        score += 0.5
    
    # Has tests (+0.5)
    if result["has_tests"]:
        score += 0.5
    
    # Has dependencies section (+0.3)
    if result["has_dependencies"]:
        score += 0.3
    
    # Has examples (+0.2)
    if result["has_examples"]:
        score += 0.2
    
    # Inject count bonus (high usage = valuable)
    if result["inject_count"] > 1000:
        score += 1  # heavily used, even if stubby, it's useful
    elif result["inject_count"] > 100:
        score += 0.5
    elif result["inject_count"] > 10:
        score += 0.2
    
    # Penalty for minimal content
    if result["file_count"] <= 1:  # only SKILL.md
        score -= 0.5
    
    # Clamp
    result["score"] = max(0, min(10, round(score, 1)))
    
    # Determine tier
    if result["score"] <= 3:
        result["tier"] = "stub"
    elif result["score"] <= 6:
        result["tier"] = "developing"
    else:
        result["tier"] = "good"
    
    return result

def print_report(all_skills, analyzed):
    """Print structured report."""
    # Count by tier
    tier_counts = collections.Counter()
    for a in analyzed:
        tier_counts[a["tier"]] += 1
    
    stubs = [a for a in analyzed if a["tier"] == "stub"]
    developing = [a for a in analyzed if a["tier"] == "developing"]
    good = [a for a in analyzed if a["tier"] == "good"]
    
    stubs_sorted = sorted(stubs, key=lambda x: x["score"])
    dev_sorted = sorted(developing, key=lambda x: x["score"], reverse=True)
    good_sorted = sorted(good, key=lambda x: x["score"], reverse=True)
    
    print("=" * 70)
    print("  技能质量审查报告 (Skill Quality Review)")
    print(f"  Skills scanned: {len(analyzed)}")
    print("=" * 70)
    print()
    
    print("─" * 70)
    print(f"  总体分布")
    print("─" * 70)
    print(f"  ★ Stub (score 0-3):     {tier_counts.get('stub', 0)}")
    print(f"  ◇ Developing (score 4-6): {tier_counts.get('developing', 0)}")
    print(f"  ✓ Good (score 7-10):    {tier_counts.get('good', 0)}")
    print()
    
    print("─" * 70)
    print(f"  🔴 最低分 5 个 Stub Skill (核心缺陷)")
    print("─" * 70)
    for a in stubs_sorted[:5]:
        name = a["full_name"]
        print(f"\n  [{a['score']}/10] {name}")
        print(f"      SKILL.md: {a['md_size']} bytes / {a['md_lines']} lines")
        print(f"      Files: {a['file_count']} (code: {a['code_file_count']})")
        print(f"      Injections: {a['inject_count']} | Effectiveness: {a['effectiveness']}")
        issues = a["issues"][:3]
        if issues:
            for iss in issues:
                print(f"      ⚠ {iss}")
        # Suggestions
        if a["md_size"] < 500:
            print(f"      💡 建议: 扩展 SKILL.md → 添加 Description / Usage / Examples 章节")
        elif not a["has_instructions"]:
            print(f"      💡 建议: 添加 Usage/Instructions/Workflow 章节")
        if not a["has_code"]:
            print(f"      💡 建议: 提供代码文件或模板实现")
        if not a["has_dependencies"]:
            print(f"      💡 建议: 声明依赖和前置条件")
    print()
    
    print("─" * 70)
    print(f"  🟡 最有升级潜力的 5 个 Developing Skill (最接近 Good)")
    print("─" * 70)
    for a in dev_sorted[:5]:
        name = a["full_name"]
        print(f"\n  [{a['score']}/10] {name}")
        print(f"      SKILL.md: {a['md_size']} bytes / {a['md_lines']} lines")
        print(f"      Files: {a['file_count']} (code: {a['code_file_count']})")
        sections = a.get("sections", [])
        print(f"      Sections: {len(sections)} present")
        if a["has_code"]:
            print(f"      ✓ 已有代码文件")
        else:
            print(f"      ✗ 缺少代码实现 — 添加代码文件可提升")
        if not a["has_examples"]:
            print(f"      ✗ 缺少示例章节 — 添加 Examples 可达 Good")
        if not a["has_dependencies"]:
            print(f"      ✗ 缺少依赖声明")
        print(f"      💡 升级路径: 添加 Examples 章节 + 代码实现 (约 2-3 个改进点即可升入 Good tier)")
    print()
    
    print("─" * 70)
    print(f"  🟢 Top 5 Good Skills (标杆)")
    print("─" * 70)
    for a in good_sorted[:5]:
        name = a["full_name"]
        print(f"\n  [{a['score']}/10] {name}")
        print(f"      SKILL.md: {a['md_size']} bytes | Files: {a['file_count']} | Code: {a['code_file_count']}")
        print(f"      Injections: {a['inject_count']}")
    print()
    
    # Priority actions
    print("─" * 70)
    print("  优先级改进行动计划")
    print("─" * 70)
    print("""
  P0 — 修复极短 SKILL.md（<500 bytes 的 stub）：
        至少补充 Description + Usage 两个章节

  P1 — 为 stub skill 添加代码实现：
        提供可执行的代码模板或示例文件 (.py/.sh)

  P2 — 补齐 developing skill 的 Examples + Dependencies 章节：
        这两个章节缺失是 developing→good 的最大瓶颈

  P3 — 激活反馈数据收集：
        skill_stats.json 中所有 skills 的 effectiveness 均为 0.5（默认值）
        positive/negative/neutral 全为 0 — 无人反馈，无法驱动改进

  P4 — 为高频使用 skill（inject_count > 1000）补充文档：
        高使用量但文档薄弱的 skill 投入产出比最高
""")
    
    # Stats
    avg_score = sum(a["score"] for a in analyzed) / len(analyzed) if analyzed else 0
    print("─" * 70)
    print(f"  统计摘要")
    print("─" * 70)
    print(f"  平均分: {avg_score:.2f}/10")
    print(f"  中位数: {sorted([a['score'] for a in analyzed])[len(analyzed)//2]:.1f}/10")
    print(f"  总分分布: ", end="")
    for tier in ["stub", "developing", "good"]:
        cnt = tier_counts.get(tier, 0)
        bar = "█" * max(1, cnt // 5)
        print(f"{tier}={cnt} {bar}  ", end="")
    print()
    
    # Files without stats
    no_stats = [a for a in analyzed if a["name"] not in stats]
    print(f"  无统计数据: {len(no_stats)} skills")

if __name__ == "__main__":
    skills = find_all_skills()
    analyzed = [analyze_skill(s) for s in skills]
    print_report(skills, analyzed)
