# PostgreSQL Backup/Restore & Retention Policy

## Scope
- Database: `portfolio_db`
- Backup format: `pg_dump` custom archive (`.dump`)
- Restore tool: `pg_restore`

## Retention
- Daily backups retained for 30 days
- Weekly backups retained for 12 weeks (recommended by scheduler policy)
- Monthly backups retained for 12 months (recommended by scheduler policy)

## Operational Commands
- Windows backup: `pwsh ./portfolio_web/ops/backup_postgres.ps1`
- Windows restore: `pwsh ./portfolio_web/ops/restore_postgres.ps1 -BackupFile <path>`
- Linux/container backup: `sh ./portfolio_web/docker/backup/backup.sh`
- Linux/container restore: `BACKUP_FILE=<path> sh ./portfolio_web/docker/backup/restore.sh`

## Scheduling Recommendations
- Production: run backup every 24h (off-peak), plus weekly and monthly jobs.
- Store backups on encrypted storage outside the primary DB host.
- Validate at least one restore test weekly in a non-production environment.

## Recovery Objective Targets
- Suggested RPO: 24 hours for MVP.
- Suggested RTO: 2 hours for MVP.

## Security
- Do not commit backup files to source control.
- Restrict backup directory access to operations/admin roles only.
- Encrypt backups at rest and in transit when exported.
