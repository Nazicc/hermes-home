#!/bin/bash
# honcho-ensure.sh — Honcho 持久化看门狗
# 用途：确保 honcho 容器在 Docker Desktop 启动后自动恢复
# 调用方：launchd (com.hermes.honcho-containers)
# 生命周期：启动后即退出（launchd KeepAlive 管理重启）
#
# 设计要点：
# - 等 Docker Desktop 就绪（最长 60 秒）
# - 检查容器是否已在运行；已健康则立即退出
# - 缺失容器则通过 docker compose 重建
# - 网络/卷不存在则自动创建

set -euo pipefail

LOG="$HOME/.hermes/logs/honcho-ensure.log"
COMPOSE_DIR="$HOME/.hermes/hermes-agent/honcho"
COMPOSE_FILE="$COMPOSE_DIR/docker-compose.yml"
NETWORK="honcho-net"
CONTAINERS=("honcho-postgres" "honcho-api" "honcho-deriver")

mkdir -p "$HOME/.hermes/logs"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

# === Step 1: 等 Docker Desktop 就绪 ===
log "等待 Docker Desktop 就绪..."
DOCKER_READY=false
for i in $(seq 1 60); do
  if docker info >/dev/null 2>&1; then
    DOCKER_READY=true
    log "Docker Desktop 就绪（耗时 ${i}s）"
    break
  fi
  sleep 1
done

if [ "$DOCKER_READY" = false ]; then
  log "ERROR: Docker Desktop 60 秒未就绪，退出"
  exit 1
fi

# === Step 2: 检查 honcho 网络 ===
if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
  log "创建网络 $NETWORK..."
  docker network create "$NETWORK"
  log "网络 $NETWORK 创建完成"
fi

# === Step 3: 检查现有容器 ===
ALL_HEALTHY=true
for c in "${CONTAINERS[@]}"; do
  STATUS=$(docker inspect "$c" --format '{{.State.Status}}' 2>/dev/null || echo "missing")
  if [ "$STATUS" = "running" ]; then
    log "[OK] $c 已在运行"
  else
    log "[!] $c 状态=${STATUS}，需要重建"
    ALL_HEALTHY=false
  fi
done

# 全部健康则直接退出
if [ "$ALL_HEALTHY" = true ]; then
  log "所有 honcho 容器运行正常，无需操作"
  exit 0
fi

# === Step 4: 通过 docker compose 重建 ===
log "通过 docker compose 重建缺失容器..."
cd "$COMPOSE_DIR"

# 确保配置文件存在
if [ ! -f "$COMPOSE_DIR/honcho-config.toml" ]; then
  # 尝试从上游位置复制
  if [ -f "$HOME/.hermes/hermes-agent/honcho-config.toml" ]; then
    cp "$HOME/.hermes/hermes-agent/honcho-config.toml" "$COMPOSE_DIR/honcho-config.toml"
    log "从 hermes-agent/ 复制配置文件"
  else
    log "ERROR: 配置文件不存在！"
    exit 1
  fi
fi

# 清理已停止的旧容器（避免名称冲突）
log "清理已停止的旧容器..."
for c in "${CONTAINERS[@]}"; do
  if docker inspect "$c" >/dev/null 2>&1; then
    docker rm -f "$c" >/dev/null 2>&1
    log "  已移除旧容器 $c"
  fi
done

docker compose -f "$COMPOSE_FILE" up -d 2>&1 | tee -a "$LOG"

# === Step 5: 等待就绪 ===
log "等待容器健康..."
sleep 5
for c in "${CONTAINERS[@]}"; do
  STATUS=$(docker inspect "$c" --format '{{.State.Status}}' 2>/dev/null || echo "missing")
  if [ "$STATUS" = "running" ]; then
    log "[OK] $c 已恢复"
  else
    log "[!] $c 恢复失败（状态=$STATUS）"
  fi
done

# 验证 API
if curl -sf http://localhost:8889/health >/dev/null 2>&1; then
  log "[OK] Honcho API 健康检查通过"
else
  log "[WARN] Honcho API 未就绪（可能仍在启动中）"
fi

log "完成"
exit 0
