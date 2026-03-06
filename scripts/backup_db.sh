#!/usr/bin/env bash
set -euo pipefail
BASEDIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="${WPS_DB_PATH:-$BASEDIR/watcher.db}"
BACKUP_DIR="${BACKUP_DIR:-$BASEDIR/backups}"
mkdir -p "$BACKUP_DIR"
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$BACKUP_DIR/watcher.db.$TS.sql"
echo "Backing up $DB_PATH to $OUT"
sqlite3 "$DB_PATH" .dump > "$OUT"
gzip -f "$OUT"
echo "Backup complete: ${OUT}.gz"