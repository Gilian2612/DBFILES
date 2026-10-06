# =============================================
# Gestor Documental - Respaldo (Windows)
# =============================================
# Guarda la base de datos y los archivos subidos en backups\backup_<fecha>\
# Uso: doble clic en backup.bat, o clic derecho aqui -> "Ejecutar con PowerShell".
#      programar-backup.ps1 lo deja corriendo todos los dias.
# Conserva los ultimos BACKUPS_A_GUARDAR respaldos (en .env, por defecto 14) y borra los mas viejos.
# (Sin tildes a proposito: Windows PowerShell 5 lee mal los acentos en archivos sin BOM.)

param(
  [string]$Log,       # archivo donde ademas se anotan los mensajes (lo usa la tarea programada)
  [switch]$SinPausa   # no esperar Enter al terminar (lo usa restaurar.ps1)
)

$Root = $PSScriptRoot
Set-Location $Root

function Escribir($msg, $color = "Gray") {
  $linea = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  Write-Host $linea -ForegroundColor $color
  if ($Log) { Add-Content -Path $Log -Value $linea }
}
function VarEnv($nombre, $defecto) {
  if (Test-Path ".env") {
    $linea = Get-Content ".env" | Where-Object { $_ -match "^$nombre=" } | Select-Object -Last 1
    if ($linea) { return $linea.Substring($nombre.Length + 1).Trim() }
  }
  return $defecto
}
function Terminar($codigo) {
  if (-not $Log -and -not $SinPausa) { Write-Host ""; Read-Host "Presiona Enter para cerrar" | Out-Null }
  exit $codigo
}

$DbUser  = VarEnv "POSTGRES_USER" "gestor_user"
$DbName  = VarEnv "POSTGRES_DB" "gestor_documental"
$Guardar = [int](VarEnv "BACKUPS_A_GUARDAR" "14")
$Dest    = Join-Path $Root ("backups\backup_" + (Get-Date -Format "yyyyMMdd_HHmmss"))

function Falla($msg) {
  Escribir "ERROR: $msg" Red
  if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
  Terminar 1
}

$estado = docker inspect -f '{{.State.Running}}' gestor_db 2>$null
if ("$estado".Trim() -ne "true") { Falla "El contenedor gestor_db no esta corriendo (Docker abierto? proyecto levantado?)." }

Escribir "Respaldando en $Dest" Cyan
New-Item -ItemType Directory -Path $Dest -Force | Out-Null

# La base se vuelca dentro del contenedor y se copia con "docker cp": asi el archivo queda byte a byte,
# sin que PowerShell cambie la codificacion (tildes y enes) ni agregue BOM.
docker exec gestor_db pg_dump -U $DbUser -d $DbName -f /tmp/db_backup.sql
if ($LASTEXITCODE -ne 0) { Falla "pg_dump fallo." }
docker cp gestor_db:/tmp/db_backup.sql (Join-Path $Dest "db_backup.sql") | Out-Null
$copiado = $LASTEXITCODE
docker exec gestor_db rm -f /tmp/db_backup.sql | Out-Null
$dump = Join-Path $Dest "db_backup.sql"
if ($copiado -ne 0 -or -not (Test-Path $dump) -or (Get-Item $dump).Length -eq 0) { Falla "No se pudo copiar el volcado de la base." }

$uploads = Join-Path $Root "uploads"
if (Test-Path $uploads) {
  Copy-Item -Path $uploads -Destination (Join-Path $Dest "uploads") -Recurse -Force -ErrorAction Stop
}

# Rotacion: conservar solo los ultimos $Guardar (restaurar.ps1 la desactiva con BACKUP_SIN_ROTAR=1)
if (-not $env:BACKUP_SIN_ROTAR) {
  $todos = @(Get-ChildItem (Join-Path $Root "backups") -Directory -Filter "backup_*" | Sort-Object Name)
  if ($todos.Count -gt $Guardar) {
    $todos | Select-Object -First ($todos.Count - $Guardar) | ForEach-Object {
      Escribir "Borrando respaldo viejo: $($_.Name)"
      Remove-Item $_.FullName -Recurse -Force
    }
  }
}

$mb = (Get-ChildItem $Dest -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Escribir ("OK: {0} ({1:N1} MB)" -f $Dest, $mb) Green
Terminar 0
