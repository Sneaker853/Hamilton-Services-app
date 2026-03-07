#!/usr/bin/env sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must be set}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

mkdir -p "$BACKUP_DIR"
FILE="$BACKUP_DIR/portfolio_db_$(date +%Y%m%d_%H%M%S).dump"

pg_dump --format=custom --file="$FILE" "$DATABASE_URL"

find "$BACKUP_DIR" -name 'portfolio_db_*.dump' -type f -mtime +"$RETENTION_DAYS" -delete

echo "Backup complete: $FILE"
