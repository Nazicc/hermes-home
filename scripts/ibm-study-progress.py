#!/usr/bin/env python3
"""
IBM Cybersecurity Analyst — 学习进度自动跟踪脚本
读取进度文件 → 计算当前阶段 → 输出今天目标 → 保存日志
被 学习提醒 cron job 调用获取当前进度上下文
"""

import json, os, sys
from datetime import date, datetime, timedelta

PROGRESS_FILE = os.path.expanduser("~/.hermes/notes/ibm-progress.json")
LOG_FILE = os.path.expanduser("~/.hermes/notes/ibm-study-log.json")
PLAN_FILE = os.path.expanduser("~/.hermes/notes/ibm-cybersecurity-learning-plan.md")

# 学习计划：14门课，4个阶段
PHASES = [
    {"name": "第一阶段·基础打底", "weeks": (1, 3), "courses": "Course 1-4",
     "detail": "Course 1: Intro to Cybersecurity Tools\nCourse 2: Roles, Processes & OS Security\nCourse 3: Compliance Framework & Standards\nCourse 4: Network Security & DB Vulns"},
    {"name": "第二阶段·核心技术", "weeks": (4, 8), "courses": "Course 5-7",
     "detail": "Course 5: Pentest, IR & Forensics\nCourse 6: Breach Response Case Studies\nCourse 7: IBM Cybersecurity Assessment"},
    {"name": "第三阶段·进阶深度", "weeks": (9, 13), "courses": "Course 8-12",
     "detail": "Course 8: Cyber Threat Intelligence\nCourse 9: Security Operations\nCourse 10: Vuln Assessment & Mgmt\nCourse 11: App Security & Secure Coding\nCourse 12: CompTIA Security+ & CYSA+"},
    {"name": "第四阶段·前沿与冲刺", "weeks": (14, 16), "courses": "Course 13-14",
     "detail": "Course 13: GenAI for Cybersecurity\nCourse 14: Job Readiness & Career Prep\n最后：总复习 + 证书获取"},
]

START_DATE = date(2026, 6, 2)  # 计划开始日（周二）

def get_current_week():
    """计算当前是第几周（1-indexed）"""
    today = date.today()
    delta = today - START_DATE
    week = delta.days // 7 + 1
    return max(1, min(week, 16)), week % 7  # (week number, day of week 0=Sun)

def get_current_phase(week):
    """根据当前周数找到对应阶段"""
    for phase in PHASES:
        ws, we = phase["weeks"]
        if ws <= week <= we:
            return phase
    return PHASES[-1]  # 超过16周返回最后阶段

def load_progress():
    """读取已有进度"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "start_date": START_DATE.isoformat(),
        "last_course": "Course 1",
        "last_topic": "",
        "completed_pct": 0,
        "last_study_date": None,
        "days_studied": 0,
        "streak": 0,
        "study_hours": 0.0,
        "current_week": 1,
    }

def save_progress(progress):
    """原子写入进度"""
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, PROGRESS_FILE)

def load_log():
    """读取学习日志"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"entries": []}

def today_str():
    return date.today().isoformat()

def main():
    today = date.today()
    week, dow = get_current_week()
    phase = get_current_phase(week)
    progress = load_progress()
    
    # 更新当前周数
    progress["current_week"] = week
    
    # 判断今天是否工作日学习日
    is_weekday = today.weekday() < 5  # Mon=0, Fri=4
    is_study_day = is_weekday  # 工作日每晚学
    is_weekend_intensive = today.weekday() == 5  # 周六集中学
    
    # 计算阶段进度
    phase_start_week = phase["weeks"][0]
    phase_end_week = phase["weeks"][1]
    phase_total = phase_end_week - phase_start_week + 1
    phase_progress = min(100, max(0, (week - phase_start_week) / phase_total * 100))
    
    # 整体进度
    overall_pct = min(100, week / 16 * 100)
    
    # 构建输出
    result = {
        "today": today_str(),
        "week": week,
        "phase": phase["name"],
        "phase_courses": phase["courses"],
        "phase_progress_pct": round(phase_progress),
        "overall_progress_pct": round(overall_pct),
        "is_study_day": is_study_day or is_weekend_intensive,
        "is_weekend_intensive": is_weekend_intensive,
        "phase_detail": phase["detail"],
        "current_course": progress.get("last_course", "Course 1"),
        "last_topic": progress.get("last_topic", ""),
        "streak": progress.get("streak", 0),
        "days_studied": progress.get("days_studied", 0),
        "study_hours": progress.get("study_hours", 0.0),
        "last_study_date": progress.get("last_study_date"),
    }
    
    # 打印 JSON 供 cron 解析
    print(json.dumps(result, ensure_ascii=False))
    return result

if __name__ == "__main__":
    main()
