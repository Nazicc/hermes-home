#!/usr/bin/env python3
"""
IBM 学习记录脚本 — 学习结束后调用，保存当天学习日志
用法: python3 ~/.hermes/scripts/ibm-study-record.py --course "Course 1" --topic "网络基础" --hours 1.5 --note "完成OSI模型章节"
"""

import argparse, json, os, sys
from datetime import date, datetime

PROGRESS_FILE = os.path.expanduser("~/.hermes/notes/ibm-progress.json")
LOG_FILE = os.path.expanduser("~/.hermes/notes/ibm-study-log.json")

def load_file(path, fallback):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return fallback

def save_file(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    # fsync parent dir
    parent_fd = os.open(os.path.dirname(path), os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)

def main():
    parser = argparse.ArgumentParser(description="记录IBM学习进度")
    parser.add_argument("--course", required=True, help="课程编号 e.g. Course 1")
    parser.add_argument("--topic", required=True, help="今天学习主题")
    parser.add_argument("--hours", type=float, required=True, help="学习时长(小时)")
    parser.add_argument("--note", default="", help="备注")
    parser.add_argument("--pct", type=int, default=0, help="该课程完成百分比")
    args = parser.parse_args()
    
    today = date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 1. 更新进度
    progress = load_file(PROGRESS_FILE, {"days_studied": 0, "streak": 0, "study_hours": 0.0, "completed_pct": 0})
    progress["last_course"] = args.course
    progress["last_topic"] = args.topic
    progress["last_study_date"] = today
    progress["days_studied"] = progress.get("days_studied", 0) + 1
    progress["study_hours"] = progress.get("study_hours", 0.0) + args.hours
    
    # 计算连续天数
    last_date_str = progress.get("last_study_date_before", "")
    if last_date_str:
        try:
            last_date = date.fromisoformat(last_date_str)
            diff = (date.today() - last_date).days
            if diff == 1:
                progress["streak"] = progress.get("streak", 0) + 1
            elif diff > 1:
                progress["streak"] = 1  # 断签重计
            # diff == 0: 同一天多次记录，不改变 streak
        except (ValueError, TypeError):
            progress["streak"] = progress.get("streak", 0) + 1
    else:
        progress["streak"] = progress.get("streak", 0) + 1
    progress["last_study_date_before"] = today
    progress["completed_pct"] = min(100, progress.get("completed_pct", 0) + args.pct)
    
    save_file(PROGRESS_FILE, progress)
    
    # 2. 添加日志
    log = load_file(LOG_FILE, {"entries": []})
    log["entries"].append({
        "date": today,
        "time": now,
        "course": args.course,
        "topic": args.topic,
        "hours": args.hours,
        "note": args.note,
        "pct": args.pct,
    })
    save_file(LOG_FILE, log)
    
    result = {
        "status": "ok",
        "days_studied": progress["days_studied"],
        "streak": progress["streak"],
        "total_hours": round(progress["study_hours"], 1),
        "completed_pct": progress["completed_pct"],
    }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
