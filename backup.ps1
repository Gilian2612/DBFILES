# =============================================
# Gestor Documental - Script de Backup (PowerShell)
# =============================================

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $PSScriptRoot "backups\backup_$Timestamp"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Iniciando Respaldo del Gestor Documental..." -ForegroundColor Cyan
Write-Host "Directorio de destino: $BackupDir" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

Write-Host "Exportando base de datos PostgreSQL..." -ForegroundColor Yellow
$dumpFile = Join-Path $BackupDir "db_backup.sql"
& docker exec gestor_db pg_dump -U gestor_user -d gestor_documental | Out-File -FilePath $dumpFile -Encoding utf8

$UploadsDir = Join-Path $PSScriptRoot "uploads"
if (Test-Path $UploadsDir) {
    Write-Host "Copiando archivos fisicos de uploads..." -ForegroundColor Yellow
    Copy-Item -Path $UploadsDir -Destination (Join-Path $BackupDir "uploads") -Recurse -Force
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "[OK] Respaldo completado exitosamente en:" -ForegroundColor Green
Write-Host "$BackupDir" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
