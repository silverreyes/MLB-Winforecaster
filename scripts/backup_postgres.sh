#!/bin/bash
# Daily Postgres backup for MLB Win Forecaster
# Cron entry: 0 3 * * * /opt/mlb-winforecaster/scripts/backup_postgres.sh >> /var/log/mlb_backup.log 2>&1

set -e

BACKUP_DIR="/opt/backups/mlb"
CONTAINER_NAME="mlb-winforecaster-db-1"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/mlb_forecaster_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "$(date): Starting backup..."

# pg_dump from the running Postgres container, pipe through gzip
docker exec "$CONTAINER_NAME" pg_dump -U mlb mlb_forecaster | gzip > "$BACKUP_FILE"

# Verify backup is non-empty
if [ $? -eq 0 ] && [ -s "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "$(date): Backup successful: $BACKUP_FILE ($SIZE)"
else
    echo "$(date): ERROR: Backup failed or produced empty file"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Remove backups older than 7 days
DELETED=$(find "$BACKUP_DIR" -name "mlb_forecaster_*.sql.gz" -mtime +7 -delete -print | wc -l)
echo "$(date): Retention cleanup complete ($DELETED old backups removed)"
