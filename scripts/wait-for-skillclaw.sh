#!/bin/bash
# wait-for-skillclaw.sh
# Hermes Gateway 启动包装脚本
# 等待 SkillClaw proxy (:30000) 就绪后再启动 gateway
# 最多等待 60 秒，每 2 秒探测一次

SERVICE_NAME="SkillClaw"
TARGET_PORT=30000
TIMEOUT=60
INTERVAL=2

echo "[$(date '+%H:%M:%S')] ⏳ 等待 $SERVICE_NAME (:${TARGET_PORT}) 就绪..."

elapsed=0
while [ $elapsed -lt $TIMEOUT ]; do
    if lsof -i :${TARGET_PORT} -P 2>/dev/null | grep -q LISTEN; then
        echo "[$(date '+%H:%M:%S')] ✅ $SERVICE_NAME 就绪（:${TARGET_PORT}）"
        break
    fi
    sleep $INTERVAL
    elapsed=$((elapsed + INTERVAL))
done

if [ $elapsed -ge $TIMEOUT ]; then
    echo "[$(date '+%H:%M:%S')] ⚠️ $SERVICE_NAME 超时(${TIMEOUT}s)，继续启动 Gateway..."
fi

echo "[$(date '+%H:%M:%S')] 🚀 启动 Hermes Gateway..."
exec /Users/can/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway run --replace
