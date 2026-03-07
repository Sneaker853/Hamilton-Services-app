param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$BackupDir = "./backups",
    [int]$RetentionDays = 30
)

if (-not $DatabaseUrl) {
    throw "DATABASE_URL is required."
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $BackupDir "portfolio_db_$timestamp.dump"

$env:PGCONNECT_TIMEOUT = "10"
pg_dump --format=custom --file="$backupFile" "$DatabaseUrl"

if ($LASTEXITCODE -ne 0) {
    throw "Backup failed with exit code $LASTEXITCODE"
}

Get-ChildItem -Path $BackupDir -Filter "portfolio_db_*.dump" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays) } |
    Remove-Item -Force

Write-Host "Backup completed: $backupFile"
