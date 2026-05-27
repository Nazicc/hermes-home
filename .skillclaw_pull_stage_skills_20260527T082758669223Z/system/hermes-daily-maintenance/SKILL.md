---
name: hermes-daily-maintenance
description: "Daily 04:00 AM maintenance job covering RSS health, hermes-agent version, code compatibility, skills/plugins/MCP compatibility, git sync, and memory system health. Runs as cron job 4b3cce3298e1, delivers to Feishu. Use when: running scheduled health checks, verifying system stability, or checking compatibility after updates. NOT for: emergency diagnostics (use hermes-diagnostics), cron script deployment (use hermes-prerun-script-deploy), or non-scheduled troubleshooting."
category: system
---

# 每日系统维护 — 凌晨自动执行

## 时间
每天 04:00 AM 执行（`0 4 * * *`）

## 注意
这是**只读检查**，不执行实际升级。仅诊断和报告。

---

## 任务清单

### 1. RSS 源健康检查
bash
python3 ~/.hermes/scripts/rss_health_checker.py


验证 6/6 源全部 healthy。如果有任何源失败（timeout/http_error/unreachable/waf_blocked）：
  - 记录失败的源名、状态、错误信息
  - 标记需要人工介入

### 2. hermes-agent 版本兼容性检查
bash
cd ~/.hermes/hermes-agent && \
  ./venv/bin/python -c "from hermes_cli import __version__; print('current:', __version__)" && \
  git fetch origin --tags && \
  LATEST=$(git describe --tags origin/main 2>/dev/null || git describe --tags origin/master 2>/dev/null) && \
  echo "latest: $LATEST"


- **hermes-agent venv Python**（`./venv/bin/python`）只有 stdlib，不含 httpx/yaml 等第三方包。脚本若需网络请求用 `urllib.request`，若需 YAML 解析用 `import json` 或 regex，避免依赖 venv 外包。
- 对比当前版本 vs 最新 tag。如果有可用更新：
  - 记录当前版本、最新版本、commit 距离
  - 标记待升级（由 `hermes update` 命令执行，不在此只读检查中执行）
  - 关联 release notes：`~/.hermes/skills/skills/hermes-daily-maintenance/RELEASE_v*.md`

### 3. 代码兼容性检查
bash
cd ~/.hermes/hermes-agent && \
  ./venv/bin/python -m py_compile hermes_cli/main.py \
    hermes_cli/plugins_cmd.py \
    hermes_cli/gateway_cmd.py \
    hermes_cli/update_cmd.py \
    tools/mcp_tool.py && \
  echo "✅ Python syntax OK" && \
  ./venv/bin/python -c "from hermes_cli import main; from hermes_cli import plugins_cmd; from tools import mcp_tool; print('✅ core imports OK')"


- `py_compile` 验证核心文件语法
- 实际 import 测试确保无运行时破坏（废弃警告也算 OK）
- 任何失败：记录文件路径 + 错误类型，标记待修

> **Python 环境**：必须使用 `~/.hermes/hermes-agent/venv/bin/python`。

### 4. Skills 兼容性检查
bash
cd ~/.hermes/hermes-agent && \
  ./venv/bin/python scripts/validate_skills.py --path ~/.hermes/skills/skills


- 使用 hermes-agent 自带 `validate_skills.py` 扫描所有 skills
- 报告 PASS/FAIL 数量
- FAIL 时：逐条记录 skill 名称 + 失败原因

另外手动扫描所有 skill 目录的 SKILL.md，验证 frontmatter：
bash
for dir in ~/.hermes/skills/skills/*/; do
    SKILL_MD="$dir/SKILL.md"
    if [ -f "$SKILL_MD" ]; then
        python3 -c "
import sys, re, yaml
content = open('$SKILL_MD').read()
match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
if not match:
    print('NO FRONTMATTER: $dir', file=sys.stderr)
else:
    fm = yaml.safe_load(match.group(1))
    required = ['name', 'description', 'category']
    missing = [k for k in required if k not in fm]
    if missing:
        print('MISSING FIELDS in $dir:', missing, file=sys.stderr)
"
    fi
done


> **Python 环境**：frontmatter 扫描脚本用系统 Python（stdlib yaml 即可，无需 httpx）。

### 5. Plugins 兼容性检查
bash
ls ~/.hermes/hermes-agent/plugins/ && \
  for p in ~/.hermes/hermes-agent/plugins/*/plugin.yaml; do
    echo "--- $p ---"
    cat "$p"
  done


- 检查 `~/.hermes/hermes-agent/plugins/` 下每个插件的 `plugin.yaml`
- 验证 `manifest_version`（当前理解 `manifest_version: 1`）
- 验证 `name`、`version` 字段存在
- 验证 `hermes_version`（如果声明）兼容当前版本
- 缺失字段或版本冲突：记录详情

> **Python 环境**：必须使用 `venv/bin/python`（hermes-agent 依赖在此 venv 内）。

### 6. MCP Servers 兼容性检查
bash
cd ~/.hermes/hermes-agent && \
  ./venv/bin/python -c "
import yaml, os, sys, importlib.util
config = yaml.safe_load(open(os.path.expanduser('~/.hermes/config.yaml')))
errors = []
for name, cfg in config.get('mcp_servers', {}).items():
    enabled = cfg.get('enabled', True)
    if not enabled:
        continue
    cmd = cfg.get('command', '')
    args = cfg.get('args', [])
    # 验证脚本类 MCP（args 最后一个参数是 .py 文件）
    if args and args[-1].endswith('.py'):
        script = os.path.expanduser(args[-1])
        if not os.path.exists(script):
            errors.append(f'MCP {name}: script not found: {script}')
        else:
            try:
                spec = importlib.util.spec_from_file_location('_mcp_test', script)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                print(f'MCP: {name} ✅ script loads OK')
            except Exception as e:
                errors.append(f'MCP {name}: script load failed: {e}')
    else:
        # 验证命令行工具存在
        if not os.path.exists(cmd) and not any(os.path.exists(os.path.join(p, cmd)) for p in os.environ.get('PATH', '').split(':')):
            errors.append(f'MCP {name}: command not found: {cmd}')
        else:
            print(f'MCP: {name} ✅ command found: {cmd}')
if errors:
    print('ERRORS:')
    for e in errors: print(e)
else:
    print('All enabled MCP servers OK')
"


- 从 `~/.hermes/config.yaml` 读取 `mcp_servers` 配置
- 验证每个 server 的 `command` 路径存在且可执行
- 验证脚本类 MCP（`.py` 结尾）的文件可访问且 import 无错
- 验证环境变量（如 `HERMES_SKILLS_DIR`）引用的路径存在
- 任何 server 失败：记录名称 + 失败原因，标记待修

> **Python 环境**：必须使用 `venv/bin/python`。
> **已知限制**：hermes-agent venv 是 stdlib-only，不含 yaml/httpx/requests。所有 MCP yaml 读取使用 stdlib。

### 7. Git 同步检查
bash
cd ~/.hermes/hermes-agent && git fetch origin && \
  STATUS=$(git status --short) && \
  if [ -n "$STATUS" ]; then echo "⚠ uncommitted changes:"; echo "$STATUS"; else echo "✅ clean"; fi && \
  BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || git rev-list --count HEAD..origin/master 2>/dev/null) && \
  if [ "$BEHIND" -gt 0 ]; then echo "⚠ $BEHIND commits behind origin"; else echo "✅ up to date"; fi


- 有未 commit 变更时记录 diff 摘要（避免大规模变更静默丢失）
- 落后 origin 时记录 commit 数量

### 8. 内存系统健康检查
bash
python3 ~/.hermes/scripts/memory_health_checker.py


或手动检查核心文件存在且非空：
bash
ls -la ~/.hermes/agent_memory.md ~/.hermes/SOUL.md && \
  python3 -c "
import os
for f in ['~/.hermes/agent_memory.md', '~/.hermes/SOUL.md']:
    f = os.path.expanduser(f)
    if not os.path.exists(f):
        print(f'⚠ {f} missing')
    elif os.path.getsize(f) == 0:
        print(f'⚠ {f} empty')
    else:
        print(f'✅ {f} OK ({os.path.getsize(f)} bytes)')
"


- 验证持久化锚点文件存在且有内容
- 空文件或缺失：标记需要人工介入

### 9. Skills Evolver 系统状态
bash
ls ~/.hermes/skills/ && \
  cd ~/.hermes/hermes-agent && \
  ./venv/bin/python -c "from skills.skill_tool import SkillTool; print('✅ SkillTool import OK')" 2>&1


- 验证 skills 目录可访问
- 验证 SkillTool 可正常导入
- Skills 数量变化趋势记录（每周对比）

---

## 输出格式

汇总所有检查结果，格式：

📋 每日系统维护报告 — YYYY-MM-DD
=== RSS ===
  ✅ 6/6 healthy
=== hermes-agent ===
  version: 0.10.0, latest: 0.10.0, status: ✅ up to date
=== Code ===
  ✅ syntax OK, ✅ imports OK
=== Skills ===
  ✅ 92/92 PASS
=== Plugins ===
  ✅ 3 plugins OK
=== MCP Servers ===
  ✅ 4/4 healthy
=== Git ===
  ✅ clean, ✅ up to date
=== Memory ===
  ✅ agent_memory.md OK, ✅ SOUL.md OK
=== Skills Evolver ===
  ✅ SkillTool OK

- 任何 FAIL/WARN 用 ⚠ 标记
- 发送至 Feishu webhook（`HERMES_FEISHU_WEBHOOK_URL`）
- FAIL 项加入"需要人工介入"清单
- 如有任何失败项，在对应行加 ❌ 前缀，并附上具体错误信息

**总结**: 无需人工介入（或列出需要人工介入的具体项）
