#!/bin/bash
# Container Watchdog — 检查 Hindsight & Honcho 容器状态，异常时自愈重启
# 静默模式：一切正常时不输出，仅在重启后输出日志
# 用作 no_agent=True cron 脚本

set -euo pipefail

HINDSIGHT_COMPOSE="/Users/can/hindsight/docker-compose.yaml"
HONCHO_COMPOSE="/Users/can/.hermes/scripts/honcho/docker-compose.yml"
LOG_FILE="/tmp/container-watchdog.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

ACTIONS=""

# ── Hindsight ──
if ! docker ps --format '{{.Names}}' | grep -q '^hindsight$'; then
  log "Hindsight 容器未运行，正在启动..."
  docker compose -f "$HINDSIGHT_COMPOSE" up -d 2>&1 | tee -a "$LOG_FILE"
  ACTIONS="${ACTIONS}hindsight "
fi

# ── Honcho ──
if ! docker ps --format '{{.Names}}' | grep -q '^honcho-api$'; then
  log "Honcho 容器未运行，正在启动..."
  docker compose -f "$HONCHO_COMPOSE" up -d 2>&1 | tee -a "$LOG_FILE"
  ACTIONS="${ACTIONS}honcho "
fi

# 有动作才输出（cron no_agent 模式下非空 stdout = 通知用户）
if [ -n "$ACTIONS" ]; then
  log "✅ 已恢复容器: ${ACTIONS}"
  echo "🧬 Container Watchdog 自愈报告"
  echo "━━━━━━━━━━━━━━━━━━━━━━━"
  echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "操作: 重启了 ${ACTIONS}"
  echo ""
  echo "--- 当前容器状态 ---"
  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null
else
  # 完全静默
  exit 0
fi
