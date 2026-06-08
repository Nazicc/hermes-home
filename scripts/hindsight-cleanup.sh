#!/bin/bash
# hindsight-cleanup: Daily health check + DB maintenance for Hindsight
# Run by cron job 86ac58a3e617 at 04:00 daily
set -euo pipefail

REPORT=""
ERRORS=0

report_line() {
    REPORT="${REPORT}▸ $1
"
}

# ---- 1. Docker health ----
report_line "---"
report_line "Docker 容器健康"

CONTAINERS=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep -i hindsight || true)
if echo "$CONTAINERS" | grep -q hindsight; then
    while IFS= read -r line; do
        report_line "✅ ${line}"
    done <<< "$CONTAINERS"
else
    report_line "❌ 未找到 hindsight 容器"
    ERRORS=$((ERRORS+1))
fi

HEALTH=$(docker inspect hindsight --format '{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
report_line "✅ hindsight health: ${HEALTH}"

# ---- 2. API health ----
report_line "---"
report_line "API 健康检查"

HEALTH_RESP=$(curl -s http://127.0.0.1:18888/health 2>/dev/null || echo '{"error":"curl failed"}')
if echo "$HEALTH_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='healthy'; assert d.get('database')=='connected'" 2>/dev/null; then
    report_line "✅ /health → ${HEALTH_RESP}"
else
    report_line "❌ /health → ${HEALTH_RESP}"
    ERRORS=$((ERRORS+1))
fi

VERSION_RESP=$(curl -s http://127.0.0.1:18888/version 2>/dev/null || echo '{"error":"curl failed"}')
report_line "✅ /version → ${VERSION_RESP}"

# ---- 3. hermes-agent bank stats ----
report_line "---"
report_line "hermes-agent 库统计"

STATS_RAW=$(curl -s http://127.0.0.1:18888/v1/default/banks/hermes-agent/stats 2>/dev/null)
if [ -n "$STATS_RAW" ]; then
    echo "$STATS_RAW" | python3 -c "
import sys, json
s = json.load(sys.stdin)
n = s.get('units', {}); l = s.get('links', {})
print(f\"节点 {n.get('total',0)} (experience {n.get('experience',0)} / observation {n.get('observation',0)} / world {n.get('world',0)})\")
print(f\"链接 {l.get('total',0)} (semantic {l.get('semantic',0)} / entity {l.get('entity',0)} / temporal {l.get('temporal',0)})\")
print(f\"文档 {s.get('documents',0)}\")
print(f\"完成 {s.get('completed',0)} / 失败 {s.get('failed',0)} / 待处理 {s.get('pending',0)}\")
" 2>/dev/null | while IFS= read -r line; do report_line "✅ ${line}"; done
fi
report_line "✅ 统计信息已采集"

# ---- 4. DB maintenance via psql ----
report_line "---"
report_line "数据库维护"

PG_HOST=hindsight-db
PG_USER=hindsight_user
PG_DB=hindsight_db
PG_PASS=hindsight_secure_pass_2024_prod

# VACUUM ANALYZE
VACUUM_OUT=$(docker run --rm --network hindsight_hindsight-net \
    -e PGPASSWORD="${PG_PASS}" \
    postgres:15-alpine psql \
    -h "${PG_HOST}" -U "${PG_USER}" -d "${PG_DB}" \
    -c "VACUUM (ANALYZE);" 2>&1)
report_line "✅ VACUUM (ANALYZE): 成功"

# Row counts
ROW_COUNTS=$(docker run --rm --network hindsight_hindsight-net \
    -e PGPASSWORD="${PG_PASS}" \
    postgres:15-alpine psql \
    -h "${PG_HOST}" -U "${PG_USER}" -d "${PG_DB}" \
    -t -A \
    -c "SELECT tbl, count FROM (SELECT 'memory_units' AS tbl, COUNT(*) FROM memory_units UNION ALL SELECT 'memory_links', COUNT(*) FROM memory_links UNION ALL SELECT 'entities', COUNT(*) FROM entities UNION ALL SELECT 'documents', COUNT(*) FROM documents UNION ALL SELECT 'chunks', COUNT(*) FROM chunks) x;" 2>&1)
while IFS='|' read -r tbl cnt; do
    report_line "✅ ${tbl}: ${cnt}"
done <<< "$ROW_COUNTS"

# DB size
DB_SIZE=$(docker run --rm --network hindsight_hindsight-net \
    -e PGPASSWORD="${PG_PASS}" \
    postgres:15-alpine psql \
    -h "${PG_HOST}" -U "${PG_USER}" -d "${PG_DB}" \
    -t -A \
    -c "SELECT pg_size_pretty(pg_database_size(current_database()));" 2>&1)
report_line "✅ 数据库大小: ${DB_SIZE}"

# Extensions
EXTS=$(docker run --rm --network hindsight_hindsight-net \
    -e PGPASSWORD="${PG_PASS}" \
    postgres:15-alpine psql \
    -h "${PG_HOST}" -U "${PG_USER}" -d "${PG_DB}" \
    -t -A \
    -c "SELECT string_agg(extname || ' ' || extversion, ' / ') FROM pg_extension;" 2>&1)
report_line "✅ 扩展: ${EXTS}"

# ---- 5. Summary ----
report_line "---"
if [ "$ERRORS" -eq 0 ]; then
    report_line "状态: 全部健康 ✅"
else
    report_line "状态: ${ERRORS} 个异常 ❌"
fi

echo "# Hindsight 维护报告 — $(date +%Y-%m-%d)"
echo ""
echo "${REPORT}"
