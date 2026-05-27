#!/bin/bash
# OpenViking 全栈健康检查脚本
# 用途：验证 OpenViking 容器 + MCP 配置完整性
# 可手动运行，也可设为 cron 定时检查
# 用法: bash ~/.hermes/scripts/check-openviking-stack.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

check() {
    local name=$1
    local result=$2
    if [ "$result" = "ok" ]; then
        echo -e "  ${GREEN}✓${NC} $name"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}✗${NC} $name — $result"
        FAIL=$((FAIL+1))
    fi
}

echo "🔍 OpenViking Stack Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Docker Desktop 运行中
if docker info >/dev/null 2>&1; then
    check "Docker Desktop" "ok"
else
    check "Docker Desktop" "Docker daemon 未运行 → 启动 Docker Desktop"
fi

# 2. OpenViking 容器状态
if docker ps --filter name=openviking --format "{{.Status}}" 2>/dev/null | grep -q "Up"; then
    check "OpenViking 容器" "ok"
else
    # 尝试重启
    if docker ps -a --filter name=openviking --format "{{.Names}}" 2>/dev/null | grep -q openviking; then
        docker start openviking >/dev/null 2>&1 && check "OpenViking 容器" "已重启" || check "OpenViking 容器" "启动失败"
    else
        # 容器不存在，尝试从 docker-compose 重建
        if [ -f ~/.openviking/docker-compose.yml ]; then
            cd ~/.openviking && docker compose up -d >/dev/null 2>&1 && check "OpenViking 容器" "已重建" || check "OpenViking 容器" "重建失败"
        else
            check "OpenViking 容器" "容器不存在且无 docker-compose.yml"
        fi
    fi
fi

# 3. OpenViking HTTP 可达
if curl -sf http://127.0.0.1:1933/health >/dev/null 2>&1; then
    check "OpenViking API (1933)" "ok"
else
    check "OpenViking API (1933)" "不可达"
fi

# 4. 配置完整性
MISSING=""
[ ! -f ~/.openviking/ov.conf ] && MISSING="$MISSING ov.conf"
[ ! -f ~/.openviking/ovcli.conf ] && MISSING="$MISSING ovcli.conf"
[ ! -d ~/.hermes/openviking-data ] && MISSING="$MISSING openviking-data"
if [ -z "$MISSING" ]; then
    check "配置文件" "ok"
else
    check "配置文件" "缺失:$MISSING"
fi

# 5. MCP Server 脚本存在
MCP_SERVER=~/.hermes/mcp-servers/openviking-mcp/openviking_mcp.py
if [ -f "$MCP_SERVER" ]; then
    if python3 -c "import ast; ast.parse(open('$MCP_SERVER').read())" 2>/dev/null; then
        check "MCP 服务器脚本" "ok"
    else
        check "MCP 服务器脚本" "语法错误"
    fi
else
    check "MCP 服务器脚本" "文件不存在: $MCP_SERVER"
fi

# 6. Plugin 存在
PLUGIN=~/.hermes/hermes-agent/plugins/memory/openviking/__init__.py
if [ -f "$PLUGIN" ]; then
    if python3 -c "import ast; ast.parse(open('$PLUGIN').read())" 2>/dev/null; then
        check "OpenViking Plugin" "ok"
    else
        check "OpenViking Plugin" "语法错误"
    fi
else
    check "OpenViking Plugin" "文件不存在"
fi

# 7. Config YAML 引用
if grep -A4 "^  openviking:" ~/.hermes/config.yaml 2>/dev/null | grep -q "enabled: true"; then
    check "config.yaml MCP 引用" "ok"
elif grep -q "openviking" ~/.hermes/config.yaml 2>/dev/null; then
    check "config.yaml MCP 引用" "存在但未启用"
else
    check "config.yaml MCP 引用" "缺少 openviking 段"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "结果: ${GREEN}$PASS 通过${NC}, ${RED}$FAIL 失败${NC}"

if [ $FAIL -gt 0 ]; then
    echo -e "${YELLOW}⚠ 部分检查未通过，请排查上述问题${NC}"
    exit 1
else
    echo -e "${GREEN}✓ 全部通过，系统运行正常${NC}"
    exit 0
fi
