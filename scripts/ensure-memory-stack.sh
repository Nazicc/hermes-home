#!/usr/bin/env bash
# ==============================================================
# ensure-memory-stack.sh — 统一内存栈恢复脚本
# 
# 职责：确保 Hindsight + Honcho Docker 容器始终运行
# 原理：幂等，可任意重复执行。仅当容器缺失时才重建。
#
# Cron:  每 5 分钟由 launchd 触发（或直接 crontab）
# Logs:  ~/.hermes/logs/ensure-memory-stack.{stdout,stderr}.log
# ==============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HONCHO_DIR="$HOME/.hermes/scripts/honcho"
HINDSIGHT_DIR="$HOME/hindsight"
LOG_DIR="$HOME/.hermes/logs"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

mkdir -p "$LOG_DIR"

log()  { echo "[$TIMESTAMP] $*" >> "$LOG_DIR/ensure-memory-stack.stdout.log"; }
err()  { echo "[$TIMESTAMP] ERROR: $*" >> "$LOG_DIR/ensure-memory-stack.stderr.log"; }
cleanup() {
  local ec=$?
  if [ $ec -ne 0 ]; then
    err "Script exited with code $ec"
  fi
}
trap cleanup EXIT

log "=== ensure-memory-stack.sh started ==="

# ----------------------------------------------------------
# 1. Docker daemon sanity
# ----------------------------------------------------------
if ! docker info &>/dev/null; then
  err "Docker daemon not reachable, skipping."
  exit 1
fi

# ----------------------------------------------------------
# 2. Hindsight
# ----------------------------------------------------------
ensure_hindsight() {
  if docker ps --format '{{.Names}}' | grep -qFx 'hindsight'; then
    log "[Hindsight] container already running, skipping."
    return 0
  fi

  if docker ps --format '{{.Names}}' | grep -qFx 'hindsight-db'; then
    log "[Hindsight] db already running, skipping."
  fi

  # 检查已停止的容器
  local stopped
  stopped=$(docker ps -a --format '{{.Names}}' | grep -E '^(hindsight|hindsight-db)$' | wc -l)
  if [ "$stopped" -gt 0 ]; then
    log "[Hindsight] Found $stopped stopped container(s), restarting..."
    cd "$HINDSIGHT_DIR" && docker compose up -d
    log "[Hindsight] Restarted from docker compose."
    return 0
  fi

  # 容器完全消失 — 重建
  log "[Hindsight] Containers missing, starting fresh..."
  cd "$HINDSIGHT_DIR" && docker compose up -d
  log "[Hindsight] Started fresh."
}

# ----------------------------------------------------------
# 3. Honcho
# ----------------------------------------------------------
ensure_honcho() {
  if docker ps --format '{{.Names}}' | grep -qFx 'honcho-api'; then
    log "[Honcho] api container already running, skipping."
    return 0
  fi

  # 检查是否有停止的容器
  local stopped
  stopped=$(docker ps -a --format '{{.Names}}' \
    | grep -E '^(honcho-postgres|honcho-api|honcho-deriver)$' | wc -l)
  if [ "$stopped" -gt 0 ]; then
    log "[Honcho] Found $stopped stopped container(s), restarting..."
    cd "$HONCHO_DIR" && docker compose up -d
    log "[Honcho] Restarted from docker compose."
    return 0
  fi

  # 容器完全消失 → 检查镜像是否存在
  if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -qFx 'honcho-api:patched-v5'; then
    log "[Honcho] Image honcho-api:patched-v5 missing, rebuilding..."
    if [ -f "$HONCHO_DIR/build-honcho.sh" ]; then
      bash "$HONCHO_DIR/build-honcho.sh"
    elif [ -f "/tmp/honcho-v3/build-honcho.sh" ]; then
      bash "/tmp/honcho-v3/build-honcho.sh"
    else
      err "[Honcho] No build script found at $HONCHO_DIR/build-honcho.sh or /tmp/honcho-v3/build-honcho.sh"
      return 1
    fi
  fi

  log "[Honcho] Starting containers..."
  cd "$HONCHO_DIR" && docker compose up -d
  log "[Honcho] Started."
}

# ----------------------------------------------------------
# 4. Execute
# ----------------------------------------------------------
ensure_hindsight
ensure_honcho

log "=== ensure-memory-stack.sh completed ==="
