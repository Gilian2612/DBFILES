# =============================================
# Gestor Documental - Restaurar un respaldo (Windows)
# =============================================
# REEMPLAZA la base de datos y los archivos subidos actuales por los de un respaldo
# (sirve con respaldos de backup.ps1, backup.bat y backup.sh).
# Antes de tocar nada hace un respaldo del estado actual.
# Uso: clic derecho -> "Ejecutar con PowerShell"   (muestra la lista para elegir)
#      o en PowerShell:  .\restaurar.ps1 backups\backup_AAAAMMDD_HHMMSS
# (Sin tildes a proposito: Windows PowerShell 5 lee mal los acentos en archivos sin BOM.)

param([string]$Origen)

function Pausa { Write-Host ""; Read-Host "Presiona Enter para cerrar" | Out-Null }
function Falla($msg) { Write-Host ""; Write-Host "ERROR: $msg" -ForegroundColor Red; Pausa; exit 1 }
function AppResponde {
  try { Invoke-WebRequest -Uri "http://localhost/health" -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true }
  catch { return $false }
}

# La ruta del argumento se resuelve desde donde se llamo al script
if ($Origen) {
  $r = Resolve-Path $Origen -ErrorAction SilentlyContinue
  if (-not $r) { Falla "No existe la carpeta $Origen." }
  $Origen = $r.Path
}

$Root = $PSScriptRoot
Set-Location $Root

function VarEnv($nombre, $defecto) {
  if (Test-Path ".env") {
    $linea = Get-Content ".env" | Where-Object { $_ -match "^$nombre=" } | Select-Object -Last 1
    if ($linea) { return $linea.Substring($nombre.Length + 1).Trim() }
  }
  return $defecto
}
$DbUser = VarEnv "POSTGRES_USER" "gestor_user"
$DbName = VarEnv "POSTGRES_DB" "gestor_documental"
# Sin comillas en los comandos SQL (PowerShell 5 las pierde al pasarlas a docker): solo nombres simples
if ($DbUser -notmatch '^[a-z_][a-z0-9_]*$' -or $DbName -notmatch '^[a-z_][a-z0-9_]*$') {
  Falla "POSTGRES_USER y POSTGRES_DB solo pueden tener minusculas, numeros y guion bajo."
}

# 1. Elegir el respaldo
if (-not $Origen) {
  $lista = @(Get-ChildItem (Join-Path $Root "backups") -Directory -Filter "backup_*" -ErrorAction SilentlyContinue | Sort-Object Name -Descending)
  if ($lista.Count -eq 0) { Falla "No hay respaldos en backups\." }
  Write-Host "Respaldos disponibles (el mas nuevo primero):"
  for ($i = 0; $i -lt $lista.Count; $i++) { Write-Host ("  {0}) {1}" -f ($i + 1), $lista[$i].Name) }
  $n = Read-Host "Numero del respaldo a restaurar"
  if ($n -notmatch '^\d+$' -or [int]$n -lt 1 -or [int]$n -gt $lista.Count) { Falla "Opcion invalida." }
  $Origen = $lista[[int]$n - 1].FullName
}
$dump = Join-Path $Origen "db_backup.sql"
if (-not (Test-Path $dump) -or (Get-Item $dump).Length -eq 0) { Falla "$Origen no tiene db_backup.sql." }

$estado = docker inspect -f '{{.State.Running}}' gestor_db 2>$null
if ("$estado".Trim() -ne "true") { Falla "El contenedor gestor_db no esta corriendo. Levanta el proyecto (instalar.ps1) y vuelve a intentar." }

# 2. Confirmar
Write-Host ""
Write-Host "Se va a restaurar: $Origen"
Write-Host "Esto REEMPLAZA la base de datos y los archivos subidos actuales." -ForegroundColor Yellow
Write-Host "Antes se hara un respaldo del estado actual."
$ok = Read-Host "Escribe SI para continuar"
if ($ok -cne "SI") { Falla "Cancelado. No se cambio nada." }

# 3. Respaldo de seguridad (sin rotacion, para no borrar el respaldo que se va a restaurar)
Write-Host ""
Write-Host "1/4 Respaldo de seguridad del estado actual..."
$env:BACKUP_SIN_ROTAR = "1"
& (Join-Path $Root "backup.ps1") -SinPausa
$resultado = $LASTEXITCODE
Remove-Item Env:BACKUP_SIN_ROTAR
if ($resultado -ne 0) { Falla "No se pudo hacer el respaldo de seguridad. No se restauro nada." }
$Seguridad = (Get-ChildItem (Join-Path $Root "backups") -Directory -Filter "backup_*" | Sort-Object Name | Select-Object -Last 1).FullName
$FalloDb = "La base quedo incompleta. El estado anterior esta en $Seguridad : restauralo con .\restaurar.ps1 `"$Seguridad`""

# 4. Base de datos (con la app detenida para que nadie escriba mientras tanto)
Write-Host "2/4 Deteniendo la app..."
docker compose stop api | Out-Null
if ($LASTEXITCODE -ne 0) { Falla "No se pudo detener la app." }

Write-Host "3/4 Restaurando la base de datos..."
docker exec gestor_db psql -U $DbUser -d postgres -q -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $DbName WITH (FORCE);" -c "CREATE DATABASE $DbName OWNER $DbUser;" | Out-Null
if ($LASTEXITCODE -ne 0) { Falla "No se pudo recrear la base. $FalloDb" }

# Se copia el archivo al contenedor (sin pasar por PowerShell, que cambiaria la codificacion),
# quitando antes el BOM que dejaban los respaldos viejos de backup.ps1
$bytes = [IO.File]::ReadAllBytes($dump)
$archivo = $dump
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
  $archivo = Join-Path $env:TEMP "gestor_restaurar.sql"
  [IO.File]::WriteAllBytes($archivo, $bytes[3..($bytes.Length - 1)])
}
docker cp $archivo gestor_db:/tmp/restaurar.sql | Out-Null
if ($LASTEXITCODE -ne 0) { Falla "No se pudo copiar el respaldo al contenedor. $FalloDb" }
docker exec gestor_db psql -U $DbUser -d $DbName -q -v ON_ERROR_STOP=1 -f /tmp/restaurar.sql | Out-Null
$cargado = $LASTEXITCODE
docker exec gestor_db rm -f /tmp/restaurar.sql | Out-Null
if ($archivo -ne $dump) { Remove-Item $archivo -Force }
if ($cargado -ne 0) { Falla "Fallo la carga del respaldo. $FalloDb" }

# 5. Archivos subidos
Write-Host "4/4 Restaurando los archivos subidos..."
$origenUploads = Join-Path $Origen "uploads"
if (Test-Path $origenUploads) {
  $temporal = Join-Path $Root "uploads.restaurando"
  if (Test-Path $temporal) { Remove-Item $temporal -Recurse -Force }
  try {
    Copy-Item -Path $origenUploads -Destination $temporal -Recurse -Force -ErrorAction Stop
    if (Test-Path (Join-Path $Root "uploads")) { Remove-Item (Join-Path $Root "uploads") -Recurse -Force -ErrorAction Stop }
    Rename-Item $temporal "uploads" -ErrorAction Stop
  } catch { Falla "No se pudieron reemplazar los archivos subidos: $($_.Exception.Message). $FalloDb" }
} else {
  Write-Host "AVISO: el respaldo no tiene carpeta uploads; se dejan los archivos actuales." -ForegroundColor Yellow
}

docker compose start api | Out-Null
if ($LASTEXITCODE -ne 0) { Falla "No se pudo volver a arrancar la app: docker compose start api" }
for ($i = 0; $i -lt 30 -and -not (AppResponde); $i++) { Start-Sleep -Seconds 2 }

Write-Host ""
Write-Host "Listo. Se restauro $Origen" -ForegroundColor Green
Write-Host "El estado anterior quedo guardado en $Seguridad"
Pausa
