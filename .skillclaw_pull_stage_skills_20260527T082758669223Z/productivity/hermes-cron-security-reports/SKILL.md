---
name: hermes-cron-security-reports
description: 定时抓取安全资讯并自动推送到飞书的 Hermes cron job 任务流程
category: productivity
---

---
name: hermes-cron-security-reports
category: productivity
description: 定时抓取安全资讯并自动推送到飞书的 Hermes cron job 任务流程
---

# Hermes Cron 安全资讯日报推送

## Trigger
定时抓取安全资讯并推送到飞书的 cron job 任务。

## 环境前提

- 工作目录: `/Users/can/.hermes/security-reports`
- 虚拟环境: `/tmp/security-venv` (必须使用此预创建的 venv，系统 Python 无 feedparser)
- 激活命令: `source /tmp/security-venv/bin/activate`
- Feishu 推送配置: 设置环境变量 `HERMES_CRON_AUTO_DELIVER_PLATFORM=feishu`（由 Hermes scheduler 自动读取）

## 执行流程

### Step 1: 抓取资讯

bash
cd /Users/can/.hermes/security-reports
source /tmp/security-venv/bin/activate
python fetch_security_news.py


> **注意**: 必须使用 `/tmp/security-venv` 虚拟环境，系统 Python 受 macOS 保护无法安装 feedparser。

### Step 2: 生成报告

bash
python generate_report.py


### Step 3: 推送到飞书

**关键**: 此 cron job 配置了 `HERMES_CRON_AUTO_DELIVER_PLATFORM=feishu`，Hermes scheduler 会在任务完成后自动将内容推送到配置的飞书频道。

- **不要**调用 `send_message` 工具 — 该工具仅在交互式上下文中可用，cron job 中不存在。
- 直接将报告内容作为最终响应返回即可，Hermes scheduler 读取环境变量并自动投递。

## 已知约束

- 虚拟环境 `/tmp/security-venv` 需预先创建（`python -m venv /tmp/security-venv` 并安装 feedparser）
- 系统 Python 无法安装包，必须使用 venv
- Feishu 推送由 Hermes scheduler 控制，不需要手动调用推送工具
