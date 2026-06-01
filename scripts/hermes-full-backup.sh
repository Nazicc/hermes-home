#!/bin/bash
# hermes-full-backup.sh
# Full backup of ~/.hermes to /Volumes/XG7/AI/hermes-backup/
# Date-named directory, keeps last 8 weeks (56 days), deletes older

set -euo pipefail

SOURCE="$HOME/.hermes"
DEST_BASE="/Volumes/XG7/AI/hermes-backup"
DATE_DIR="hermes-backup-$(date +%Y-%m-%d)"
DEST="$DEST_BASE/$DATE_DIR"
RETENTION_DAYS=56  # 8 weeks

echo "▸ 备份源     $SOURCE"
echo "▸ 目标路径   $DEST"

# Create destination
mkdir -p "$DEST"

# rsync: preserve permissions, timestamps, symlinks, sparse files
# Exclude large caches, venvs, node_modules, temp files
echo "▸ 开始同步..."
rsync -aAX --delete \
  --exclude='venv/' \
  --exclude='node_modules/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.hermes/cache/' \
  --exclude='.hermes/tmp/' \
  --exclude='**/.git/' \
  --exclude='logs/' \
  --exclude='audio_cache/' \
  --exclude='state-snapshots/' \
  --exclude='.env' \
  --info=progress2 \
  "$SOURCE/" "$DEST/" 2>&1

RSYNC_EXIT=$?
if [ $RSYNC_EXIT -ne 0 ] && [ $RSYNC_EXIT -ne 24 ]; then
  # Exit 24 = partial transfer due to vanished source files (harmless)
  echo "❌ rsync 失败 (exit=$RSYNC_EXIT)"
  exit $RSYNC_EXIT
fi

echo "▸ 保留最近 ${RETENTION_DAYS} 天（8 周）备份，删除更旧的..."

# List and delete old backups
mapfile -t OLD_BACKUPS < <(find "$DEST_BASE" -maxdepth 1 -type d -name 'hermes-backup-*' | sort -r | tail -n +2)

DELETED=0
while IFS= read -r dir; do
  dir_date="${dir##hermes-backup-}"
  dir_epoch=$(date -j -f "%Y-%m-%d" "${dir##*-}" "+%s" 2>/dev/null || echo 0)
  now_epoch=$(date "+%s")
  age_days=$(( (now_epoch - dir_epoch) / 86400 ))
  if [ "$age_days" -gt "$RETENTION_DAYS" ]; then
    echo "  删除旧备份: $(basename "$dir") (已存 ${age_days} 天)"
    rm -rf "$dir"
    DELETED=$((DELETED + 1))
  fi
done < <(find "$DEST_BASE" -maxdepth 1 -type d -name 'hermes-backup-*' | sort)

# Count total backups
TOTAL=$(find "$DEST_BASE" -maxdepth 1 -type d -name 'hermes-backup-*' | wc -l | tr -d ' ')

# Get backup size
BACKUP_SIZE=$(du -sh "$DEST" 2>/dev/null | awk '{print $1}')

echo ""
echo "▸ 备份完成 ✅"
echo "▸ 本次备份   $BACKUP_SIZE"
echo "▸ 已删除     ${DELETED} 个旧备份"
echo "▸ 现有备份   ${TOTAL} 个"
echo "▸ 位置       $DEST"
