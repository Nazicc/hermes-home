#!/usr/bin/env python3
"""memU MCP Server — 回归测试套件。

验证：
  1. 脚本语法正确（可导入）
  2. FastMCP 初始化正常
  3. 所有 4 个工具正确注册
  4. 环境变量和配置有效
  5. config.yaml 条目正确
"""

import importlib.util
import os
import subprocess
import sys
import yaml
from pathlib import Path

HERMES_HOME = os.path.expanduser("~/.hermes")
SCRIPT_PATH = os.path.join(HERMES_HOME, "scripts", "memu_mcp.py")
VENV_PYTHON = os.path.join(HERMES_HOME, "memu-venv", "bin", "python")
CONFIG_PATH = os.path.join(HERMES_HOME, "config.yaml")
ENV_PATH = os.path.join(HERMES_HOME, ".env")

PASS = 0
FAIL = 0


def check(description: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    if ok:
        print(f"  ✅ {description}")
        PASS += 1
    else:
        print(f"  ❌ {description}")
        if detail:
            for line in detail.splitlines():
                print(f"     {line}")
        FAIL += 1


def section(name: str):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


# ════════════════════════════════════════════════════════════════
section("1. 基础环境检查")
# ════════════════════════════════════════════════════════════════

check("venv python 存在",
      os.path.isfile(VENV_PYTHON))

check("脚本文件存在",
      os.path.isfile(SCRIPT_PATH))

check("脚本可读",
      os.access(SCRIPT_PATH, os.R_OK))

# ════════════════════════════════════════════════════════════════
section("2. Python 导入与语法检查")
# ════════════════════════════════════════════════════════════════

# 编译检查
result = subprocess.run(
    [VENV_PYTHON, "-m", "py_compile", SCRIPT_PATH],
    capture_output=True, text=True, timeout=15
)
check("Python 语法编译通过", result.returncode == 0, result.stderr)

# 关键依赖检查
deps = [
    ("mcp", "from mcp.server.fastmcp import FastMCP"),
    ("memu-py", "from memu.app.service import MemoryService"),
]
for dep_name, import_stmt in deps:
    result = subprocess.run(
        [VENV_PYTHON, "-c", import_stmt],
        capture_output=True, text=True, timeout=15
    )
    check(f"依赖 {dep_name} 可导入",
          result.returncode == 0, result.stderr)

# ════════════════════════════════════════════════════════════════
section("3. 环境变量配置")
# ════════════════════════════════════════════════════════════════

# 检查 .env 是否存在
env_ok = os.path.isfile(ENV_PATH)
check(".env 文件存在", env_ok)

if env_ok:
    env_vars = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env_vars[k] = v

    # 需要的环境变量
    needed = [
        ("SILICONFLOW_API_KEY", "MEMU_EMBEDDING_API_KEY 的来源"),
        ("DEEPSEEK_API_KEY", "MEMU_LLM_API_KEY 的来源"),
    ]
    for var, purpose in needed:
        check(f" {var} 在 .env 中定义（{purpose}）",
              var in env_vars and env_vars[var].strip(),
              f"当前值: {env_vars.get(var, '<未定义>')[:8]}...")

# ════════════════════════════════════════════════════════════════
section("4. config.yaml memu MCP 条目")
# ════════════════════════════════════════════════════════════════

if os.path.isfile(CONFIG_PATH):
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    mcp_config = config.get("mcp_servers", {})
    memu_entry = mcp_config.get("memu")

    if memu_entry:
        check("memu MCP server 已启用",
              memu_entry.get("enabled", False))
        check("command 指向 memu-venv python",
              memu_entry.get("command") == VENV_PYTHON,
              f"期望: {VENV_PYTHON}\n实际: {memu_entry.get('command')}")
        check("args 指向 memu_mcp.py",
              len(memu_entry.get("args", [])) >= 1 and
              "memu_mcp.py" in memu_entry["args"][-1],
              f"实际 args: {memu_entry.get('args')}")
        check("env 节存在并包含 MEMU_DATABASE_URL",
              "MEMU_DATABASE_URL" in memu_entry.get("env", {}),
              f"env keys: {list(memu_entry.get('env', {}).keys())}")
        check("MEMU_EMBEDDING_MODEL = BAAI/bge-m3",
              memu_entry.get("env", {}).get("MEMU_EMBEDDING_MODEL") == "BAAI/bge-m3")
    else:
        check("memu MCP 条目存在于 config.yaml", False, "未在 mcp_servers 下找到 memu 条目")
else:
    check("config.yaml 存在", False)

# ════════════════════════════════════════════════════════════════
section("5. FastMCP 与工具注册验证")
# ════════════════════════════════════════════════════════════════

# 从脚本中提取工具名和 MCP 服务器识别
tool_names = []
with open(SCRIPT_PATH) as f:
    for line in f:
        line = line.strip()
        if line.startswith("@mcp.tool") or "def memu_" in line:
            if "def memu_" in line:
                name = line.split("def ")[1].split("(")[0].strip()
                tool_names.append(name)

expected = {"memu_memorize", "memu_retrieve", "memu_list_memories", "memu_evolution_status"}
check(f"工具注册：期望 {len(expected)} 个",
      len(tool_names) == len(expected),
      f"找到: {tool_names}")
check("memu_memorize 已注册", "memu_memorize" in tool_names)
check("memu_retrieve 已注册", "memu_retrieve" in tool_names)
check("memu_list_memories 已注册", "memu_list_memories" in tool_names)
check("memu_evolution_status 已注册", "memu_evolution_status" in tool_names)

# 检查 FastMCP 构造器使用 instructions 而非已废弃的 description
with open(SCRIPT_PATH) as f:
    content = f.read()
# 检查 FastMCP( 调用块（参数可能在下一行）
lines = content.splitlines()
fastmcp_idxs = [i for i, l in enumerate(lines) if "FastMCP(" in l and "tool" not in l.split("(")[0]]
fastmcp_block_has_description = False
fastmcp_block_has_instructions = False
for idx in fastmcp_idxs:
    # 从 FastMCP( 所在行开始，读取直到 ) 结束
    block = "\n".join(lines[idx:idx+6])  # 6 行足够覆盖多行参数
    if "description=" in block:
        fastmcp_block_has_description = True
    if "instructions=" in block:
        fastmcp_block_has_instructions = True
check("FastMCP 构造器使用 instructions 参数（非已废弃 description）",
      not fastmcp_block_has_description and fastmcp_block_has_instructions,
      f"FastMCP 调用行: {[lines[i] for i in fastmcp_idxs]}")

# ════════════════════════════════════════════════════════════════
section("6. 启动测试（模拟 MCP 握手）")
# ════════════════════════════════════════════════════════════════

# 尝试通过 stdio 启动，发送一个简单的 JSON-RPC 请求验证快速初始化不崩溃
# 注意：实际的 MCP 初始化需要完整工具列表，这里只验证启动不崩溃
proc = subprocess.Popen(
    [VENV_PYTHON, SCRIPT_PATH],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env={"PATH": os.environ.get("PATH", ""),
         "HOME": os.environ.get("HOME", "")},
)
try:
    # 给进程一点时间等它打印 stderr 启动消息后进入 main loop
    import time
    time.sleep(1)
    # 发送初始化请求
    init_request = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"memu-regression-test","version":"1.0.0"}}}\n'
    proc.stdin.write(init_request)
    proc.stdin.flush()
    time.sleep(2)
    # 检查进程是否还活着
    poll = proc.poll()
    check("MCP 进程收到 initialize 请求后存活",
          poll is None,
          f"进程已退出，exit_code={poll}")
    # 如果活着，发送 shutdown
    if proc.poll() is None:
        proc.stdin.write('{"jsonrpc":"2.0","id":2,"method":"shutdown","params":{}}\n')
        proc.stdin.flush()
        time.sleep(0.5)
        proc.terminate()
except Exception as e:
    check("MCP 启动测试通过", False, str(e))
finally:
    if proc.poll() is None:
        proc.terminate()
        proc.wait(timeout=5)

# ════════════════════════════════════════════════════════════════
section("7. 工具调用快速验证（微基准）")
# ════════════════════════════════════════════════════════════════

# 验证每个工具函数的签名（参数名）是否完整
tool_signatures = {}
current_tool = None
with open(SCRIPT_PATH) as f:
    for line in f:
        stripped = line.strip()
        if stripped.startswith("async def memu_"):
            current_tool = stripped.split("def ")[1].split("(")[0].strip()
            tool_signatures[current_tool] = {"params": [], "return": None}
        elif current_tool and stripped.startswith("    "):
            # Collect param names from def line
            pass

# Re-scan def lines for param names
import re
with open(SCRIPT_PATH) as f:
    content = f.read()

for name in expected:
    pattern = rf"async def {name}\(([^)]+)\)"
    m = re.search(pattern, content)
    if m:
        params = m.group(1).split(",")
        param_names = [p.strip().split(":")[0].strip() for p in params if p.strip() and p.strip() != "self"]
        # 第一个参数通常是 text 或 memory_type 等
        check(f"{name} — 参数完整（{len(param_names)}个）",
              len(param_names) >= 1,
              f"参数: {param_names}")

# ════════════════════════════════════════════════════════════════
summary = f"{'='*60}\n"
summary += f"  结果: {PASS} 通过 / {FAIL} 失败 / {PASS+FAIL} 总计\n"
if FAIL > 0:
    summary += f"  ⚠️  {FAIL} 个检查未通过，请修复后重试。\n"
else:
    summary += "  ✅ 全部通过！\n"
summary += f"{'='*60}"
print(summary)

sys.exit(1 if FAIL > 0 else 0)
