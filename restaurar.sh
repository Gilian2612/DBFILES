#!/bin/bash
# =============================================
# Gestor Documental - Restaurar un respaldo (Mac / Linux)
# =============================================
# REEMPLAZA la base de datos y los archivos subidos actuales por los de un respaldo
# (sirve con respaldos de backup.sh, backup.ps1 y backup.bat).
# Antes de tocar nada hace un respaldo del estado actual.
# Uso: ./restaurar.sh                                 (muestra la lista para elegir)
#      ./restaurar.sh backups/backup_AAAAMMDD_HHMMSS

fail() { echo ""; echo "ERROR: $*"; exit 1; }

# La ruta del argumento se resuelve desde donde se llamó al script
[ -n "$1" ] && { ORIGEN="$(cd "$1" 2>/dev/null && pwd)" || fail "No existe la carpeta $1."; }

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1

env_var() { [ -f .env ] && grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
DB_USER=$(env_var POSTGRES_USER); DB_USER=${DB_USER:-gestor_user}
DB_NAME=$(env_var POSTGRES_DB);   DB_NAME=${DB_NAME:-gestor_documental}

if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"; else COMPOSE="docker-compose"; fi

# 1. Elegir el respaldo
if [ -z "$ORIGEN" ]; then
  LISTA=()
  while read -r d; do LISTA+=("$d"); done < <(ls -d backups/backup_* 2>/dev/null | sort -r)
  [ ${#LISTA[@]} -gt 0 ] || fail "No hay respaldos en backups/."
  echo "Respaldos disponibles (el más nuevo primero):"
  for i in "${!LISTA[@]}"; do echo "  $((i + 1))) ${LISTA[$i]#backups/}"; done
  read -r -p "Número del respaldo a restaurar: " N
  [[ "$N" =~ ^[0-9]+$ ]] && [ "$N" -ge 1 ] && [ "$N" -le ${#LISTA[@]} ] || fail "Opción inválida."
  ORIGEN="$ROOT/${LISTA[$((N - 1))]}"
fi
[ -s "$ORIGEN/db_backup.sql" ] || fail "$ORIGEN no tiene db_backup.sql."

docker inspect -f '{{.State.Running}}' gestor_db 2>/dev/null | grep -q true \
  || fail "El contenedor gestor_db no está corriendo. Levanta el proyecto (instalar.command) y vuelve a intentar."

# 2. Confirmar
echo ""
echo "Se va a restaurar: $ORIGEN"
echo "Esto REEMPLAZA la base de datos y los archivos subidos actuales."
echo "Antes se hará un respaldo del estado actual."
read -r -p "Escribe SI para continuar: " OK
[ "$OK" = "SI" ] || fail "Cancelado. No se cambió nada."

# 3. Respaldo de seguridad (sin rotación, para no borrar el respaldo que se va a restaurar)
echo ""
echo "1/4 Respaldo de seguridad del estado actual..."
BACKUP_SIN_ROTAR=1 ./backup.sh || fail "No se pudo hacer el respaldo de seguridad. No se restauró nada."
SEGURIDAD=$(ls -d backups/backup_* | sort | tail -1)

# 4. Base de datos (con la app detenida para que nadie escriba mientras tanto)
echo "2/4 Deteniendo la app..."
$COMPOSE stop api >/dev/null || fail "No se pudo detener la app."

echo "3/4 Restaurando la base de datos..."
FALLO_DB="La base quedó incompleta. El estado anterior está en $SEGURIDAD: restáuralo con ./restaurar.sh $SEGURIDAD"
docker exec gestor_db psql -U "$DB_USER" -d postgres -q -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS \"$DB_NAME\" WITH (FORCE);" \
    -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";" >/dev/null \
  || fail "No se pudo recrear la base. $FALLO_DB"
# Quita el BOM que deja Windows PowerShell 5 al principio de los respaldos hechos con backup.ps1
LC_ALL=C sed $'1s/^\xef\xbb\xbf//' "$ORIGEN/db_backup.sql" \
  | docker exec -i gestor_db psql -U "$DB_USER" -d "$DB_NAME" -q -v ON_ERROR_STOP=1 >/dev/null \
  || fail "Falló la carga del respaldo. $FALLO_DB"

# 5. Archivos subidos
echo "4/4 Restaurando los archivos subidos..."
if [ -d "$ORIGEN/uploads" ]; then
  rm -rf uploads.restaurando
  cp -Rp "$ORIGEN/uploads" uploads.restaurando || fail "No se pudieron copiar los archivos. $FALLO_DB"
  rm -rf uploads && mv uploads.restaurando uploads || fail "No se pudo reemplazar la carpeta uploads. $FALLO_DB"
else
  echo "AVISO: el respaldo no tiene carpeta uploads; se dejan los archivos actuales."
fi

$COMPOSE start api >/dev/null || fail "No se pudo volver a arrancar la app: $COMPOSE start api"
for _ in $(seq 1 30); do curl -fs -m 2 http://localhost/health >/dev/null 2>&1 && break; sleep 2; done

echo ""
echo "Listo. Se restauró $ORIGEN"
echo "El estado anterior quedó guardado en $SEGURIDAD"
