#!/bin/bash
# start-stack.sh
# Hermes + SkillClaw 启动保障脚本
# 确保服务按正确的启动顺序加载，验证全部就绪
# 适用于：系统重启后、launchd 服务未加载时手动修复
#
# 启动依赖链:
#   skillclaw-proxy (:30000) ───→ skillclaw-evolve (同属proxy管理)
#                                    └──→ skillclaw-key-reloader (独立launchd)
#   （proxy就绪后） gateway-wrapper ←── gateway (:8642) launchd
#                                                └──→ bridge-sync (one-shot,定时)
#   logrotate (独立定时任务，无依赖)
#
# 使用方法:
#   ./start-stack.sh                    # 全自动启动
#   ./start-stack.sh --dry-run          # 仅检查，不修改
#   ./start-stack.sh --status           # 仅报告当前状态
#   ./start-stack.sh --repair           # 尝试自动修复问题

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
HEALTHCHECK="$HERMES_HOME/scripts/healthcheck.py"
BOOTSTRAP_LOG="$HERMES_HOME/logs/stack-bootstrap.log"

DRY_RUN=false
STATUS_ONLY=false
REPAIR=false

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --status)  STATUS_ONLY=true ;;
        --repair)  REPAIR=true ;;
    esac
done

log() {
    local ts
    ts="$(date '+%H:%M:%S')"
    echo "[$ts] $*" | tee -a "$BOOTSTRAP_LOG"
}

run() {
    log "▶ $*"
    if [ "$DRY_RUN" = true ]; then
        log "  (dry-run, skipped)"
        return 0
    fi
    "$@"
}

# === Status-only mode ===
if [ "$STATUS_ONLY" = true ]; then
    echo "=== 当前服务状态 ==="
    if [ -f "$HEALTHCHECK" ]; then
        python3 "$HEALTHCHECK"
    else
        echo "健康检查脚本未找到: $HEALTHCHECK"
        echo "---"
        for plist in skillclaw skillclaw-evolve skillclaw-key-reloader gateway logrotate bridge-sync; do
            label=""
            case "$plist" in
                skillclaw) label="com.hermes.skillclaw" ;;
                skillclaw-evolve) label="ai.hermes.skillclaw-evolve" ;;
                skillclaw-key-reloader) label="com.hermes.skillclaw-key-reloader" ;;
                gateway) label="ai.hermes.gateway" ;;
                logrotate) label="ai.hermes.logrotate" ;;
                bridge-sync) label="ai.hermes.bridge-sync" ;;
            esac
            out="$(launchctl list "$label" 2>&1 || true)"
            pid="$(echo "$out" | grep -o '"PID" = [0-9]*' | grep -o '[0-9]*' || true)"
            if [ -n "$pid" ]; then
                echo "  ✓ $plist (PID $pid)"
            else
                echo "  ⚠ $plist not loaded"
            fi
        done
    fi
    # 端口检查
    echo "---"
    for port in 30000 8642; do
        if lsof -i :$port -P 2>/dev/null | grep -q LISTEN; then
            echo "  ✓ port $port"
        else
            echo "  ✗ port $port"
        fi
    done
    exit 0
fi

# === 主启动流程 ===
echo ""
echo "=================================================="
echo "  🚀 Hermes + SkillClaw 堆栈启动"
echo "=================================================="
log "开始时间: $(date)"
log ""

# Step 1: 加载所有 launchd plist
log "Step 1/4: 注册 launchd 服务..."
PLISTS=(
    "com.hermes.skillclaw.plist"
    "ai.hermes.skillclaw-evolve.plist"
    "com.hermes.skillclaw-key-reloader.plist"
    "ai.hermes.gateway.plist"
)
for plist in "${PLISTS[@]}"; do
    plist_path="$LAUNCH_AGENTS/$plist"
    label="${plist%.plist}"
    if [ ! -f "$plist_path" ]; then
        log "  ⚠ plist 不存在: $plist_path (跳过)"
        continue
    fi
    # 检查是否已加载
    if launchctl list "$label" 2>/dev/null | grep -q '"PID"'; then
        log "  ✓ $label (already loaded)"
        continue
    fi
    if [ "$DRY_RUN" = true ]; then
        log "  ~ $label (would bootstrap)"
        continue
    fi
    log "  ▶ bootstrap $label..."
    if launchctl bootstrap gui/501 "$plist_path" 2>/dev/null; then
        log "  ✓ $label loaded"
    else
        log "  ⚠ $label bootstrap failed (may already be loaded)"
    fi
done

# Step 2: 等待 SkillClaw proxy 就绪
log ""
log "Step 2/4: 等待 SkillClaw proxy (:30000) 就绪..."
TIMEOUT=60
INTERVAL=2
elapsed=0
proxy_ready=false
while [ $elapsed -lt $TIMEOUT ]; do
    if lsof -i :30000 -P 2>/dev/null | grep -q LISTEN; then
        proxy_ready=true
        log "  ✅ proxy 就绪 (port 30000)"
        break
    fi
    sleep $INTERVAL
    elapsed=$((elapsed + INTERVAL))
done

if [ "$proxy_ready" = false ]; then
    log "  ⚠ proxy 超时(${TIMEOUT}s)，继续后续检查..."
fi

# Step 3: 验证 gateway 是否通过 launchd 就绪
log ""
log "Step 3/4: 验证 Gateway (:8642)..."
GATEWAY_TIMEOUT=30
elapsed=0
gateway_ready=false
while [ $elapsed -lt $GATEWAY_TIMEOUT ]; do
    if lsof -i :8642 -P 2>/dev/null | grep -q LISTEN; then
        gateway_ready=true
        log "  ✅ gateway 就绪 (port 8642)"
        break
    fi
    sleep $INTERVAL
    elapsed=$((elapsed + INTERVAL))
done

if [ "$gateway_ready" = false ]; then
    log "  ⚠ gateway 未就绪"
    # 检查是否被 launchd 管理
    gw_out="$(launchctl list ai.hermes.gateway 2>&1 || true)"
    if echo "$gw_out" | grep -q '"PID"'; then
        pid="$(echo "$gw_out" | grep -o '"PID" = [0-9]*' | grep -o '[0-9]*')"
        log "  ⚠ gateway launchd PID $pid 但端口未就绪"
    elif echo "$gw_out" | grep -q "Could not find service"; then
        log "  ⚠ gateway launchd 未加载"
        if [ "$REPAIR" = true ] && [ -f "$LAUNCH_AGENTS/ai.hermes.gateway.plist" ]; then
            log "  ▶ 重新加载 gateway..."
            launchctl bootstrap gui/501 "$LAUNCH_AGENTS/ai.hermes.gateway.plist" 2>/dev/null || true
        fi
    fi
fi

# Step 4: 运行健康检查
log ""
log "Step 4/4: 运行健康检查..."
if [ -f "$HEALTHCHECK" ]; then
    if [ "$DRY_RUN" = false ]; then
        python3 "$HEALTHCHECK" 2>&1 | tee -a "$BOOTSTRAP_LOG"
        HC_EXIT=${PIPESTATUS[0]}
        if [ "$HC_EXIT" -eq 0 ]; then
            log "  ✅ 健康检查通过！"
        elif [ "$HC_EXIT" -eq 1 ]; then
            log "  ⚠ 健康检查: 降级状态 (有警告)"
        else
            log "  ❌ 健康检查失败 (exit $HC_EXIT)"
        fi
    fi
else
    log "  ⚠ healthcheck.py 不存在: $HEALTHCHECK"
fi

log ""
log "完成时间: $(date)"
echo "=================================================="
