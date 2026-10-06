# =============================================
# Gestor Documental - Programar respaldo diario (Windows)
# =============================================
# Crea una tarea en el Programador de tareas que corre backup.ps1 todos los dias.
# Uso: clic derecho -> "Ejecutar con PowerShell"           (todos los dias a las 23:00)
#      o en PowerShell:  .\programar-backup.ps1 -Hora 2     (otra hora, de 0 a 23)
#                        .\programar-backup.ps1 -Quitar     (quitar la tarea)
# Si el equipo esta apagado o suspendido a esa hora, el respaldo corre en cuanto se pueda.
# Docker Desktop tiene que estar abierto (activar "Start Docker Desktop when you sign in"). Log: logs\backup.log
# (Sin tildes a proposito: Windows PowerShell 5 lee mal los acentos en archivos sin BOM.)

param(
  [int]$Hora = 23,
  [switch]$Quitar
)

$Root = $PSScriptRoot
$Nombre = "Gestor Documental - Respaldo"

function Pausa { Write-Host ""; Read-Host "Presiona Enter para cerrar" | Out-Null }
function Falla($msg) { Write-Host ""; Write-Host "ERROR: $msg" -ForegroundColor Red; Pausa; exit 1 }

if ($Quitar) {
  Unregister-ScheduledTask -TaskName $Nombre -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Respaldo automatico quitado."
  Pausa; exit 0
}

if ($Hora -lt 0 -or $Hora -gt 23) { Falla "La hora debe ser un numero de 0 a 23." }

$logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Path $logs -Force | Out-Null

$argumentos = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Log "{1}"' -f (Join-Path $Root "backup.ps1"), (Join-Path $logs "backup.log")
$accion     = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argumentos -WorkingDirectory $Root
$disparador = New-ScheduledTaskTrigger -Daily -At ("{0:D2}:00" -f $Hora)
$ajustes    = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

try {
  Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparador -Settings $ajustes `
    -Description "Respaldo diario de la base de datos y los archivos del Gestor Documental" -Force -ErrorAction Stop | Out-Null
} catch { Falla "No se pudo crear la tarea: $($_.Exception.Message)" }

$guardar = "14"
if (Test-Path (Join-Path $Root ".env")) {
  $linea = Get-Content (Join-Path $Root ".env") | Where-Object { $_ -match "^BACKUPS_A_GUARDAR=" } | Select-Object -Last 1
  if ($linea) { $guardar = $linea.Substring(18).Trim() }
}

Write-Host ("Respaldo automatico programado todos los dias a las {0}:00." -f $Hora) -ForegroundColor Green
Write-Host "  Respaldos: $Root\backups   (se guardan los ultimos $guardar; cambiar con BACKUPS_A_GUARDAR en .env)"
Write-Host "  Log:       $logs\backup.log"
Write-Host "  Probar ya: Start-ScheduledTask -TaskName '$Nombre'"
Pausa
