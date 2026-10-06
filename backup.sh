#!/bin/bash
# =============================================
# Gestor Documental - Respaldo (Mac / Linux)
# =============================================
# Guarda la base de datos y los archivos subidos en backups/backup_<fecha>/.
# Uso: ./backup.sh   (programar-backup.command lo deja corriendo todos los días)
# Conserva los últimos BACKUPS_A_GUARDAR respaldos (.env, por defecto 14) y borra los más viejos.
# Los archivos que no cambiaron se enlazan al respaldo anterior (rsync --link-dest), así no ocupan doble.

set -o pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1

env_var() { [ -f .env ] && grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
DB_USER=$(env_var POSTGRES_USER);     DB_USER=${DB_USER:-gestor_user}
DB_NAME=$(env_var POSTGRES_DB);       DB_NAME=${DB_NAME:-gestor_documental}
GUARDAR=$(env_var BACKUPS_A_GUARDAR); GUARDAR=${GUARDAR:-14}

DEST="backups/backup_$(date +%Y%m%d_%H%M%S)"
log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { log "ERROR: $*"; rm -rf "$DEST"; exit 1; }

docker inspect -f '{{.State.Running}}' gestor_db 2>/dev/null | grep -q true \
  || fail "El contenedor gestor_db no está corriendo (¿Docker abierto? ¿proyecto levantado?)."

log "Respaldando en $DEST"
ANTERIOR=$(ls -d backups/backup_*/uploads 2>/dev/null | sort | tail -1)
mkdir -p "$DEST" || fail "No se pudo crear $DEST."

docker exec gestor_db pg_dump -U "$DB_USER" -d "$DB_NAME" > "$DEST/db_backup.sql" || fail "pg_dump falló."
[ -s "$DEST/db_backup.sql" ] || fail "El volcado de la base quedó vacío."

if [ -d uploads ]; then
  if [ -n "$ANTERIOR" ] && command -v rsync >/dev/null 2>&1; then
    rsync -a --link-dest="$ROOT/$ANTERIOR" uploads/ "$DEST/uploads/" || fail "No se pudieron copiar los archivos subidos."
  else
    cp -Rp uploads "$DEST/uploads" || fail "No se pudieron copiar los archivos subidos."
  fi
fi

# Rotación: conservar solo los últimos $GUARDAR (restaurar.sh la desactiva con BACKUP_SIN_ROTAR=1)
if [ -z "$BACKUP_SIN_ROTAR" ]; then
  TOTAL=$(ls -d backups/backup_* 2>/dev/null | wc -l | tr -d ' ')
  if [ "$TOTAL" -gt "$GUARDAR" ]; then
    ls -d backups/backup_* | sort | head -n $((TOTAL - GUARDAR)) | while read -r viejo; do
      log "Borrando respaldo viejo: $viejo"
      rm -rf "$viejo"
    done
  fi
fi

log "OK: $DEST ($(du -sh "$DEST" | cut -f1))"
