# =============================================
# Gestor Documental - Instalacion (Windows)
# =============================================
# Levanta el proyecto en este equipo.
# Uso: clic derecho -> "Ejecutar con PowerShell"
#      o en PowerShell:  powershell -ExecutionPolicy Bypass -File .\instalar.ps1
# Se puede correr las veces que haga falta: no borra datos ni pisa un .env existente.
# (Sin tildes a proposito: Windows PowerShell 5 lee mal los acentos en archivos sin BOM.)

$Root = $PSScriptRoot
Set-Location $Root

function Pausa { Write-Host ""; Read-Host "Presiona Enter para cerrar" | Out-Null }
function Falla($msg) { Write-Host ""; Write-Host "ERROR: $msg" -ForegroundColor Red; Pausa; exit 1 }
function DockerCorre { docker info *> $null; return ($LASTEXITCODE -eq 0) }
function AppResponde {
  try { Invoke-WebRequest -Uri "http://localhost/health" -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true }
  catch { return $false }
}
function HexAleatorio([int]$bytes) {
  $b = New-Object byte[] $bytes
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
  return -join ($b | ForEach-Object { $_.ToString("x2") })
}

Write-Host "=== Gestor Documental - instalacion ===" -ForegroundColor Cyan
Write-Host ""

# 1. Docker instalado y corriendo
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Falla "Docker no esta instalado. Instala Docker Desktop (https://www.docker.com/products/docker-desktop/) y vuelve a correr este archivo."
}
if (-not (DockerCorre)) {
  $dockerDesktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dockerDesktop) { Write-Host "Abriendo Docker Desktop..."; Start-Process $dockerDesktop }
  Write-Host "Esperando a que Docker arranque (hasta 3 minutos)..."
  for ($i = 0; $i -lt 90 -and -not (DockerCorre); $i++) { Start-Sleep -Seconds 2 }
  if (-not (DockerCorre)) { Falla "Docker no arranco. Abrelo a mano, espera a que diga que esta corriendo y vuelve a correr este archivo." }
}
Write-Host "Docker esta corriendo."

docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Falla "No se encontro 'docker compose'. Actualiza Docker Desktop." }

# 2. Archivo .env (solo si no existe; se generan contrasenas aleatorias)
if (Test-Path ".env") {
  Write-Host "Ya existe un .env, se usa el actual."
} else {
  if (-not (Test-Path ".env.example")) { Falla "Falta .env.example en la carpeta del proyecto." }
  $texto = [IO.File]::ReadAllText((Join-Path $Root ".env.example"), [Text.Encoding]::UTF8)
  $texto = $texto -replace '(?m)^POSTGRES_PASSWORD=[^\r\n]*', ("POSTGRES_PASSWORD=" + (HexAleatorio 24))
  $texto = $texto -replace '(?m)^SECRET_KEY=[^\r\n]*', ("SECRET_KEY=" + (HexAleatorio 32))
  # UTF-8 sin BOM: Docker Compose no entiende el BOM
  [IO.File]::WriteAllText((Join-Path $Root ".env"), $texto, (New-Object Text.UTF8Encoding $false))
  Write-Host "Se creo .env con contrasenas aleatorias (no lo compartas ni lo subas a git)."
}

# 3. Construir y levantar los contenedores
Write-Host ""
Write-Host "Construyendo y levantando los contenedores (la primera vez tarda unos minutos)..."
docker compose up -d --build --remove-orphans
if ($LASTEXITCODE -ne 0) { Falla "No se pudieron levantar los contenedores. Si dice que el puerto 80 esta ocupado, cierra el programa que lo usa (por ejemplo IIS o Skype)." }

# 4. Esperar a que la app responda
Write-Host ""
Write-Host "Esperando a que la app responda..."
for ($i = 0; $i -lt 60 -and -not (AppResponde); $i++) { Start-Sleep -Seconds 2 }
if (-not (AppResponde)) { Falla "La app no respondio en 2 minutos. Revisa el log con: docker compose logs api" }

# 5. Firewall: permitir el puerto 80 en redes privadas (requiere ejecutar como administrador)
$regla = "Gestor Documental (puerto 80)"
$esAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (Get-NetFirewallRule -DisplayName $regla -ErrorAction SilentlyContinue) {
  Write-Host "La regla de firewall '$regla' ya existe."
} elseif ($esAdmin) {
  New-NetFirewallRule -DisplayName $regla -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow -Profile Private | Out-Null
  Write-Host "Se creo la regla de firewall '$regla' (solo redes privadas)."
} else {
  Write-Host ""
  Write-Host "AVISO: si otros equipos no pueden entrar, vuelve a correr este archivo como administrador" -ForegroundColor Yellow
  Write-Host "       para crear la regla de firewall del puerto 80 (solo redes privadas)." -ForegroundColor Yellow
}

# 6. Direcciones para entrar
$lan = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.|100\.)' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Docker|Tailscale|Loopback' } |
  Select-Object -First 1 -ExpandProperty IPAddress
$tsCli = (Get-Command tailscale -ErrorAction SilentlyContinue).Source
if (-not $tsCli) { $tsCli = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe" }
$ts = $null
if (Test-Path $tsCli) { $ts = & $tsCli ip -4 2>$null | Select-Object -First 1 }

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "Listo. El Gestor Documental esta corriendo." -ForegroundColor Green
Write-Host ""
Write-Host "  En este equipo:          http://localhost"
if ($lan) { Write-Host "  Desde el mismo WiFi:     http://$lan" }
if ($ts)  { Write-Host "  Por Tailscale:           http://$ts" }
Write-Host "  Documentacion de la API: http://localhost/docs"
Write-Host ""
Write-Host "Usuario inicial: admin@gestor.local / Admin1234 (solo para pruebas)."
Write-Host "============================================" -ForegroundColor Green
Pausa
