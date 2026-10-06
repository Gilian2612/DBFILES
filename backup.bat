@echo off
REM =============================================
REM Gestor Documental - Respaldo (Windows)
REM =============================================
REM Atajo para doble clic: ejecuta backup.ps1, que es el que hace el respaldo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup.ps1" %*
