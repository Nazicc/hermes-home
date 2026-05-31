---
name: hermes-agent-daily-maintenance
description: "Use when performing daily health checks on hermes-agent (04:00 cron) including RSS feeds, Git status, script synchronization, memory system, Cron job status, and 5 compatibility verifications (version/code/py_compile+import/Skills/Plugins/MCP). Delivers results to Feishu. Read-only checks only — does NOT execute upgrades or modifications. NOT for: executing upgrades or modifications, emergency troubleshooting (use hermes-diagnostics for SQLite state analysis), manual diagnostics, or non-hermes-agent systems."
category: general
---

## 目标

建立完全自动化的每日凌晨维护流程（04:00 via cron），无需人工干预。诊断结果推送飞书（`deliver: origin`），有问题才告警。

## 前提条件

- hermes-agent 安装在 `~/.hermes/hermes-agent/`
- jobs.json 在 `~/.hermes/cron/jobs.json`（repo 外，敏感 prompt 不入 git）
- 只读检查，不执行实际升级（避免破坏性操作）
- 所有脚本无外部依赖（使用 stdlib）
- Python venv 在 `~/.hermes/hermes-agent/venv/bin/python3`

## 环境路径

| 路径 | 用途 |
|------|------|
| `~/.hermes/hermes-agent/` | hermes-agent repo |
| `~/.hermes/hermes_cli/` | hermes_cli 包（独立于 agent） |
| `~/.hermes/cron/jobs.json` | Cron job 定义（repo 外，用户空间） |
| `~/.hermes/scripts/` | 预运行/检查脚本 |
| `~/.hermes/config.yaml` | MCP server 配置 |
| `~/.hermes/memory/` | 内存系统目录 |
| `~/.hermes/skills/` | Skills 目录 |
| `~/.hermes/state.db` | SQLite 状态数据库 |

## 每日检查清单（10 项）

### 1. RSS 源健康检查

优先使用 stdlib urllib（无外部依赖）：

python
import urllib.request, xml.etree.ElementTree as ET

FEEDS = [
    "https://hnrss.org/frontpage",
    "https://rsshub.app/github/commits/heid疲倦/dotfiles",
    "https://rsshub.app/github/commits/heid疲倦/hermes-agent",
    "https://rsshub.app/twitter/user/lexfridman",
    "https://rsshub.app/arxiv/cs.AI/new"
]
for url in FEEDS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "hermes/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            ET.fromstring(r.read())
    except Exception as e:
        report(f"RSS FAIL {url}: {e}")


也支持使用 curl 检查 HTTP 状态：

bash
for url in "${SOURCES[@]}"; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url")
  if [ "$STATUS" -ne 200 ]; then
    echo "RSS FAIL: $url (HTTP $STATUS)"
  fi
done


### 2. Git 状态检查

bash
cd ~/.hermes/hermes-agent && git fetch origin && git status -uno


- 不 pull，只检查是否有未同步 commit
- 有 remote commits → 告警并列出 commit hash + message
- 同时检查本地状态：

bash
git status --short
git log --oneline -3


未提交改动 = 标记告警（但不阻止）。特别注意 `credential_pool.py`（key 轮换逻辑）。

### 3. 脚本同步检查

bash
cd ~/.hermes/hermes-agent && make deploy


- 确认 `scripts/rss_health_check.py`、`scripts/validate_skills.py` 存在
- 确认 `scripts/` 下无异常新增（潜在安全风险）
- 无报错 = 成功

### 4. 内存系统健康检查

bash
ls ~/.hermes/memory/  # 确认目录存在
du -sh ~/.hermes/memory/  # 大小检查


SimpleMem MCP 连通性测试（如可用）：

python
try:
    from sirchmunk import SimpleMCP
    mc = SimpleMCP()
    print('SimpleMem MCP: OK')
except ImportError:
    print('SimpleMem MCP: NOT INSTALLED')
except Exception as e:
    print(f'SimpleMem MCP: ERROR {e}')


空目录或权限错误 = 告警

### 5. Cron Job 状态检查

- 读取 `~/.hermes/cron/jobs.json`
- 确认每日 04:00 job 存在且 enabled
- 确认无过期或重复的 job

bash
python3 -c "
import json
with open('~/.hermes/cron/jobs.json') as f:
    jobs = json.load(f)
print(f'Cron jobs configured: {len(jobs)}')
for job in jobs:
    status = 'DISABLED' if job.get('disabled') else 'ENABLED'
    print(f'  - {job.get(\"id\", \"?\")}: {status} | {job.get(\"name\", \"?\")}')
"


已知 job IDs:
- `4b3cce3298e1` — 每日健康检查
- `0a8d143a2d88` — 每周升级

如果大部分 job 被禁用，记录⚠️警告。

### 6. hermes-agent 版本兼容性检查

bash
cd ~/.hermes/hermes-agent && git fetch origin && git diff origin/main HEAD --stat

# hermes_cli 版本（独立包）
python3 -c "import hermes_cli; print(f'hermes_cli: {hermes_cli.__version__}')"

# hermes-agent 版本（agent 内部）
grep '__version__' ~/.hermes/hermes-agent/hermes_cli/__init__.py


当前基准版本：`0.10.0`。版本号变化或文件差异 = 告警。

### 7. 代码兼容性检查（py_compile + import）

bash
# hermes_cli（独立包）
cd ~/.hermes/hermes_cli
python3 -m py_compile *.py
python3 -c "import hermes_cli"

# hermes-agent
cd ~/.hermes/hermes-agent
python3 -m py_compile agent/ tools/ hermes_cli/
python3 -c "import agent; import tools; import hermes_cli"


py_compile 验证语法正确性，import 测试验证模块级依赖完整性。失败 → 告警，列出具体的 import error。

### 8. Skills 健康检查

bash
cd ~/.hermes && python3 scripts/validate_skills.py

# 或手动检查
ls skills/*/SKILL.md | wc -l  # 应 >= 150


也支持 yaml.safe_load 解析检查：

bash
for skill in ~/.hermes/skills/*/SKILL.md; do
    python3 -c "
import yaml, sys
with open('$skill') as f:
    d = yaml.safe_load(f)
name = d.get('name', 'UNKNOWN')
desc = d.get('description', '')[:50]
print(f'OK: {name} | {desc}...')
"
done


### 9. Plugins 健康检查

bash
ls ~/.hermes/plugins/ 2>/dev/null || echo "无 plugins 目录（正常）"
ls ~/.hermes/hermes-agent/plugins/ 2>/dev/null || echo "无 agent plugins 目录"


如插件目录存在，检查可导入性：

bash
cd ~/.hermes/hermes-agent && python3 -c "import plugins"

for plugin in plugins/*/; do
    if [ -f "$plugin/__init__.py" ]; then
        python3 -c "
import sys, importlib.util
import os
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location('plugin', '$plugin/__init__.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
if hasattr(mod, 'check_compatibility'):
    result = mod.check_compatibility()
    print(f'PLUGIN OK: $plugin {result}')
else:
    print(f'PLUGIN SKIP: $plugin (no check_compatibility)')
" 2>&1 || echo "FAIL: $plugin"
    fi
done


### 10. MCP Server 健康检查

bash
cat ~/.hermes/config.yaml

python3 -c "
import yaml
with open('~/.hermes/config.yaml') as f:
    cfg = yaml.safe_load(f)
mcp_servers = cfg.get('mcp_servers', {})
for name, conf in mcp_servers.items():
    print(f'MCP: {name} -> {conf}')
"

# 验证关键进程
ps aux | grep -E '(deerflow|simplemem|sirchmunk)' | grep -v grep || echo "MCP processes: none running"

# 检查 MCP CLI 是否可用
mcp list 2>&1 || echo "MCP CLI not available"


已知 MCP servers: `database`, `websearch`, `filesystem`, `github`（或 sirchmunk, simplemem, simplemem_evolution, skills-quality，取决于配置）

DeerFlow 不可用（端口 1933 无响应）= 记录但不阻止其他检查。

## 5 项兼容性检查总结

| # | 检查项 | 方法 |
|---|--------|------|
| 1 | hermes-agent 版本 | `__version__` vs `origin/main` |
| 2 | 代码兼容性 | `py_compile` + `import` |
| 3 | Skills 完整性 | `validate_skills.py` 或 yaml 解析 |
| 4 | Plugins | 目录遍历 + `__init__.py` + `check_compatibility()` |
| 5 | MCP Servers | `config.yaml` 解析 + import + `mcp list` |

## 额外检查（可选）

### 活跃会话清理检查

python
import sqlite3, os
db = os.path.expanduser('~/.hermes/state.db')
if os.path.exists(db):
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL')
    orphan = cur.fetchone()[0]
    print(f'活跃会话: {orphan}')
    if orphan > 5:
        print('⚠️ 警告: 大量孤儿会话（可能需要清理）')
    cur.execute('SELECT id, started_at FROM sessions ORDER BY started_at ASC LIMIT 3')
    for row in cur.fetchall():
        print(f'  最老会话: {row[0]} from {row[1]}')
    conn.close()
else:
    print('state.db 不存在')


已知问题：历史上出现过 20 个孤儿会话（从 4 月 19 日开始），这些会话从未正确关闭。如果发现 >5 个活跃会话，检查它们是否真的在运行。

### MiniMax API Key 轮换机制检查

bash
# 检查 current_minimax_key 文件格式（是 JSON 元数据，不是纯 key）
cat ~/.skillclaw/shared/hermes-team/current_minimax_key

# 检查 skillclaw_key_reloader.py 热重载机制
ls ~/.hermes/hermes-agent/venv/lib/python*/site-packages/skillclaw/key_rotation/skillclaw_key_reloader.py 2>/dev/null
# SIGUSR1 信号应该能触发 key 重载


## 已知故障模式

| 故障 | 症状 | 处理 |
|------|------|------|
| DeerFlow 不可用 | 端口 1933 无响应，deer-flow-repo 不存在 | 记录但不阻止其他检查 |
| 孤儿会话积累 | >5 个 `ended_at IS NULL` 的会话 | 建议后续清理 |
| Cron Jobs 禁用 | 大部分 job 的 `disabled: true` | 记录到报告 |
| credential_pool.py 未提交 | Git status 显示改动 | 记录但不自动提交 |
| hermes-diagnostics 不可用 | skill not found | 跳过，跳到其他检查 |

## Cron Job 注册


{
  "id": "4b3cce3298e1",
  "name": "hermes-daily-maintenance",
  "schedule": "0 4 * * *",
  "enabled": true,
  "timezone": "Asia/Shanghai",
  "trigger": { "type": "schedule" },
  "notify_on_failure": true,
  "deliver": "origin",
  "prompt": "执行每日健康检查：RSS + Git + 脚本同步 + 内存 + Cron + 五项兼容性（版本/代码/Skills/Plugins/MCP）。推送结果到飞书。问题才告警。"
}


将 job 追加到 `~/.hermes/cron/jobs.json`。

## 告警策略

- 所有检查中**任何一项失败** → 告警（飞书通知）
- 全部通过 → 仅 deliver:origin 记录，不主动告警
- 告警内容：失败项名称 + 具体错误信息（不夸大）

## 推送格式


🏥 hermes-agent 每日维护报告
时间: {date}

✅ 正常项: RSS源, Skills({n}), Cron Jobs
⚠️ 警告项: {warnings}
❌ 失败项: {failures}

详细:
- RSS: {rss_status}
- Git: {git_status}
- 脚本同步: OK
- 内存: OK
- Cron: 运行中
- 版本: {version}
- 代码: ✓
- Skills: {n}/✓
- Plugins: ✓
- MCP: {n}/✓
- 活跃会话: {session_count}


失败时推送飞书卡片，红色高亮失败项。

## 相关 Job

| Job ID | 用途 | 关系 |
|--------|------|------|
| `4b3cce3298e1` | 每日健康检查 | 本 skill |
| `0a8d143a2d88` | 每周升级 | 独立 job |

## 约束

- 只读检查，不执行实际升级（upgrade 属于 weekly-upgrade job 职责）
- 所有脚本无外部依赖（使用 stdlib urllib、py_compile）
- 飞书推送（deliver: origin）
- 不修改 hermes-agent 本身
- 不适用于非 hermes-agent 系统
- 不适用于实时调试或一次性命令

## NOT for

- 执行实际升级操作
- 非 hermes-agent 系统的维护
- 需要网络写操作的任务
- 紧急事故响应（使用 hermes-diagnostics）
