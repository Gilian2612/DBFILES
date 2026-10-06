#!/bin/bash
# Levanta el Gestor Documental en este equipo (Mac o Linux). Doble clic en Mac, o ./instalar.command
# Se puede correr las veces que haga falta: no borra datos ni pisa un .env existente.

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1

pause() { [ -t 0 ] && { echo ""; read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."; echo ""; }; }
fail()  { echo ""; echo "ERROR: $1"; pause; exit 1; }

echo "=== Gestor Documental — instalación ==="
echo ""

# 1. Docker instalado y corriendo
command -v docker >/dev/null 2>&1 || fail "Docker no está instalado. Instala Docker Desktop (https://www.docker.com/products/docker-desktop/) y vuelve a correr este archivo."

if ! docker info >/dev/null 2>&1; then
  if [ "$(uname)" = "Darwin" ]; then
    echo "Abriendo Docker Desktop..."
    open -a Docker || fail "No se pudo abrir Docker Desktop."
  fi
  echo "Esperando a que Docker arranque (hasta 2 minutos)..."
  for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
  docker info >/dev/null 2>&1 || fail "Docker no arrancó. Ábrelo a mano, espera a que diga que está corriendo y vuelve a correr este archivo."
fi
echo "Docker está corriendo."

if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE="docker-compose"
else fail "No se encontró 'docker compose'. Actualiza Docker Desktop."; fi

# 2. Archivo .env (solo si no existe; se generan contraseñas aleatorias)
if [ -f .env ]; then
  echo "Ya existe un .env, se usa el actual."
else
  [ -f .env.example ] || fail "Falta .env.example en la carpeta del proyecto."
  command -v openssl >/dev/null 2>&1 || fail "Falta openssl para generar las contraseñas. Crea el .env a mano copiando .env.example."
  sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 24)|" \
      -e "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" \
      .env.example > .env
  chmod 600 .env
  echo "Se creó .env con contraseñas aleatorias (no lo compartas ni lo subas a git)."
fi

# 3. Construir y levantar los contenedores
echo ""
echo "Construyendo y levantando los contenedores (la primera vez tarda unos minutos)..."
$COMPOSE up -d --build --remove-orphans || fail "No se pudieron levantar los contenedores. Si dice que el puerto 80 está ocupado, cierra el programa que lo usa."

# 4. Esperar a que la app responda
echo ""
echo "Esperando a que la app responda..."
for _ in $(seq 1 60); do curl -fs -m 2 http://localhost/health >/dev/null 2>&1 && break; sleep 2; done
curl -fs -m 2 http://localhost/health >/dev/null 2>&1 \
  || fail "La app no respondió en 2 minutos. Revisa el log con: $COMPOSE logs api"

# 5. Direcciones para entrar
LAN_IP=""
if [ "$(uname)" = "Darwin" ]; then
  LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
else
  LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
TS_CLI="tailscale"
[ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ] && TS_CLI=/Applications/Tailscale.app/Contents/MacOS/Tailscale
TS_IP=$("$TS_CLI" ip -4 2>/dev/null | head -1)

echo ""
echo "============================================"
echo "Listo. El Gestor Documental está corriendo."
echo ""
echo "  En este equipo:         http://localhost"
[ -n "$LAN_IP" ] && echo "  Desde el mismo WiFi:    http://$LAN_IP"
[ -n "$TS_IP" ]  && echo "  Por Tailscale:          http://$TS_IP"
echo "  Documentación de la API: http://localhost/docs"
echo ""
echo "Usuario inicial: admin@gestor.local / Admin1234 (solo para pruebas)."
echo "============================================"
pause
