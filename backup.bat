@echo off
setlocal enabledelayedexpansion

REM =============================================
REM Gestor Documental - Script de Backup
REM =============================================

for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value 2^>nul') do set "dt=%%a"
if not defined dt (
    for /f "usebackq" %%a in (`powershell -Command "Get-Date -Format yyyyMMdd_HHmmss"`) do set "TIMESTAMP=%%a"
) else (
    set "TIMESTAMP=%dt:~0,4%%dt:~4,2%%dt:~6,2%_%dt:~8,2%%dt:~10,2%%dt:~12,2%"
)

set "BACKUP_DIR=backups\backup_%TIMESTAMP%"

echo ============================================
echo Iniciando Respaldo del Gestor Documental...
echo ============================================
echo Creando directorio: %BACKUP_DIR%
mkdir "%BACKUP_DIR%" 2>nul

echo Exportando base de datos PostgreSQL...
docker exec gestor_db pg_dump -U gestor_user -d gestor_documental > "%BACKUP_DIR%\db_backup.sql"

if exist uploads (
    echo Copiando archivos fisicos de uploads...
    xcopy uploads "%BACKUP_DIR%\uploads\" /E /I /Y /Q >nul
)

echo.
echo ============================================
echo [OK] Respaldo completado exitosamente en:
echo %BACKUP_DIR%
echo ============================================
echo.
