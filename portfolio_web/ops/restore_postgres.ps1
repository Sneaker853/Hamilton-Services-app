param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,
    [string]$DatabaseUrl = $env:DATABASE_URL
)

if (-not (Test-Path $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}

if (-not $DatabaseUrl) {
    throw "DATABASE_URL is required."
}

pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$DatabaseUrl" "$BackupFile"

if ($LASTEXITCODE -ne 0) {
    throw "Restore failed with exit code $LASTEXITCODE"
}

Write-Host "Restore completed from: $BackupFile"
