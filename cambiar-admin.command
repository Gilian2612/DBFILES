#!/bin/bash
# =============================================
# Gestor Documental - Cambiar contraseña del admin (Mac / Linux)
# =============================================
# Uso: doble clic en el archivo, o desde terminal: ./cambiar-admin.command
# Úsalo cuando no puedas iniciar sesión. Si ya entraste, cámbiala desde el perfil (▾).

fail() { echo ""; echo "ERROR: $*"; read -r -p "Presiona Enter para cerrar..."; exit 1; }

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== Gestor Documental — Cambiar contraseña del administrador ==="
echo ""

docker inspect -f '{{.State.Running}}' gestor_api 2>/dev/null | grep -q true \
  || fail "El proyecto no está corriendo. Ejecuta instalar.command primero."

read -r -s -p "Nueva contraseña (mínimo 8 caracteres): " NUEVA_PASS
echo ""
read -r -s -p "Confirmar contraseña: " CONFIRMAR_PASS
echo ""

[ "$NUEVA_PASS" = "$CONFIRMAR_PASS" ] || fail "Las contraseñas no coinciden."
[ "${#NUEVA_PASS}" -ge 8 ]            || fail "La contraseña debe tener al menos 8 caracteres."

RESULTADO=$(printf '%s\n' "$NUEVA_PASS" | docker exec -i gestor_api python3 - <<'PYEOF'
import sys, os, bcrypt
sys.path.insert(0, '/app')
from core.config import get_db
from models.models import Usuario

pw = sys.stdin.readline().rstrip('\n').encode()
if not pw:
    print("ERROR: contraseña vacía")
    sys.exit(1)

hashed = bcrypt.hashpw(pw, bcrypt.gensalt()).decode()

db = next(get_db())
try:
    user = db.query(Usuario).filter(Usuario.email == 'admin@gestor.local').first()
    if not user:
        print("ERROR: usuario admin@gestor.local no encontrado en la base de datos")
        sys.exit(1)
    user.password_hash = hashed
    db.commit()
    print("ok")
except Exception as e:
    db.rollback()
    print(f"ERROR: {e}")
    sys.exit(1)
finally:
    db.close()
PYEOF
) || fail "No se pudo conectar al contenedor."

[ "$RESULTADO" = "ok" ] || fail "$RESULTADO"

echo ""
echo "Contraseña actualizada correctamente para admin@gestor.local"
echo ""
read -r -p "Presiona Enter para cerrar..."
