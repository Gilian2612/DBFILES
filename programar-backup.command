#!/bin/bash
# Programa backup.sh para que corra solo todos los días (Mac, con launchd). Doble clic o ./programar-backup.command
# Hora: 23:00 por defecto. Para otra hora: HORA_BACKUP=2 ./programar-backup.command
# Para quitarlo:                            ./programar-backup.command --quitar
# Si la Mac está dormida a esa hora, el respaldo corre al despertar. Log: logs/backup.log

ROOT="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.gestordocumental.backup"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
HORA="${HORA_BACKUP:-23}"

pause() { [ -t 0 ] && { echo ""; read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."; echo ""; }; }
fail()  { echo ""; echo "ERROR: $1"; pause; exit 1; }

if [ "$(uname)" != "Darwin" ]; then
  echo "Este script es para Mac. En Linux, agrega esta línea con 'crontab -e':"
  echo "  0 $HORA * * * cd \"$ROOT\" && ./backup.sh >> logs/backup.log 2>&1"
  exit 0
fi

if [ "$1" = "--quitar" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
  rm -f "$PLIST"
  echo "Respaldo automático quitado."
  pause; exit 0
fi

[[ "$HORA" =~ ^([01]?[0-9]|2[0-3])$ ]] || fail "HORA_BACKUP debe ser un número de 0 a 23."

case "$ROOT" in
  "$HOME/Desktop"*|"$HOME/Documents"*|"$HOME/Downloads"*)
    fail "El proyecto está en Escritorio, Documentos o Descargas, y macOS no deja que las tareas automáticas lean esas carpetas. Muévelo a otra carpeta (ej.: ~/gestor-documental) y vuelve a correr este archivo." ;;
esac

DOCKER_BIN="$(command -v docker)"
[ -n "$DOCKER_BIN" ] || fail "No se encontró docker. Instala Docker Desktop."

chmod +x "$ROOT/backup.sh"
mkdir -p "$ROOT/logs" "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>              <string>$LABEL</string>
  <key>ProgramArguments</key>   <array><string>/bin/bash</string><string>$ROOT/backup.sh</string></array>
  <key>WorkingDirectory</key>   <string>$ROOT</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$HORA</integer><key>Minute</key><integer>0</integer></dict>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>$(dirname "$DOCKER_BIN"):$HOME/.docker/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string></dict>
  <key>StandardOutPath</key>    <string>$ROOT/logs/backup.log</string>
  <key>StandardErrorPath</key>  <string>$ROOT/logs/backup.log</string>
</dict>
</plist>
EOF
plutil -lint "$PLIST" >/dev/null || fail "El archivo de configuración quedó mal formado: $PLIST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" || fail "launchctl no pudo cargar la tarea."

GUARDAR=$(grep -E "^BACKUPS_A_GUARDAR=" "$ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2-)
echo "Respaldo automático programado todos los días a las $HORA:00."
echo "  Respaldos: $ROOT/backups   (se guardan los últimos ${GUARDAR:-14}; cambiar con BACKUPS_A_GUARDAR en .env)"
echo "  Log:       $ROOT/logs/backup.log"
echo "  Probar ya: launchctl kickstart gui/$(id -u)/$LABEL"
pause
