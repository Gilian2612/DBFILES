# Gestor Documental Multiusuario

Sistema de gestión y búsqueda documental con servidor central y múltiples clientes.

**Stack:** FastAPI + PostgreSQL + Docker + HTML/JS vanilla

> Decisiones de diseño, alternativas descartadas y pendientes: [DECISIONS.md](DECISIONS.md).

---

## Levantar el proyecto

Requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado. El puerto 80 debe estar libre.

### Opción automática

- **Mac / Linux:** doble clic en **`instalar.command`**, o desde la Terminal: `./instalar.command`
- **Windows:** clic derecho en **`instalar.ps1`** → *Ejecutar con PowerShell*.
  Si se ejecuta como administrador, también crea la regla del firewall para el puerto 80 (solo redes privadas).

El script:
- abre Docker si está cerrado;
- crea el `.env` con contraseñas aleatorias, si no existe;
- levanta los contenedores;
- espera a que la app responda y muestra las direcciones para entrar (local, WiFi y Tailscale).

Se puede correr las veces que haga falta: no borra datos ni pisa un `.env` existente.

Si macOS no deja abrirlo porque el proyecto se bajó como zip, corre esto una vez desde la carpeta del proyecto:
`xattr -dr com.apple.quarantine . && chmod +x *.command *.sh`.

### Opción manual (cualquier sistema)

1. Crear el `.env` copiando el ejemplo:
   ```bash
   cp .env.example .env
   ```
2. Editar el `.env` y cambiar `POSTGRES_PASSWORD` y `SECRET_KEY` por valores largos y aleatorios, por ejemplo con `openssl rand -hex 32`.
   - **No cambiar** `POSTGRES_USER` ni `POSTGRES_DB`: los scripts de backup usan esos nombres.
   - Los límites de subida y de login son opcionales; ver los comentarios en `.env.example`.
3. Levantar:
   ```bash
   docker compose up -d --build
   ```

### Direcciones

- App (página + API): http://localhost
- Docs API:           http://localhost/docs

> **La base de datos se crea solo la primera vez** (con `db/init.sql`). Si después se cambia el `.env`, la base sigue con lo anterior.
> Para empezar de cero: `docker compose down -v`. **Esto borra todos los datos.**

FastAPI sirve tanto la API como el frontend (`frontend/index.html`), en el puerto 80.
La base de datos (5432) no se publica fuera de Docker.

---

## Respaldos

Cada respaldo guarda la base de datos y los archivos subidos en `backups/backup_<fecha>/`.
Se conservan los últimos 14; el número se cambia con `BACKUPS_A_GUARDAR` en el `.env`.
Los respaldos son compatibles entre sistemas: uno hecho en Windows se puede restaurar en Mac, y al revés.

| Qué | Mac / Linux | Windows |
|---|---|---|
| Respaldar ahora | `./backup.sh` | doble clic en `backup.bat` |
| Respaldo automático diario (23:00) | doble clic en `programar-backup.command` | clic derecho en `programar-backup.ps1` → *Ejecutar con PowerShell* |
| Otra hora, ej. 2:00 | `HORA_BACKUP=2 ./programar-backup.command` | `.\programar-backup.ps1 -Hora 2` |
| Quitar el automático | `./programar-backup.command --quitar` | `.\programar-backup.ps1 -Quitar` |
| Restaurar | `./restaurar.sh` (muestra la lista) | clic derecho en `restaurar.ps1` → *Ejecutar con PowerShell* |

- El respaldo automático necesita que el equipo esté encendido y Docker Desktop abierto. Si a esa hora estaba apagado o suspendido, corre en cuanto se pueda. El registro queda en `logs/backup.log`.
- En Mac, el proyecto **no puede estar** en Escritorio, Documentos ni Descargas, porque macOS no deja que las tareas automáticas lean esas carpetas.
- **Restaurar reemplaza** la base y los archivos actuales. Pide escribir `SI` para confirmar, y antes hace un respaldo del estado actual.
- En Linux, el respaldo diario se programa con `cron`; `programar-backup.command` muestra la línea a agregar.

---

## Credenciales por defecto

| Email               | Contraseña | Rol   |
|---------------------|------------|-------|
| admin@gestor.local  | Admin1234  | admin |

**Cambiar la contraseña en producción.**

---

## Estructura

```
gestor-documental/
├── docker-compose.yml
├── instalar.command        # levanta todo (Mac/Linux)
├── instalar.ps1            # levanta todo (Windows)
├── backup.sh / backup.ps1 / backup.bat           # respaldo
├── restaurar.sh / restaurar.ps1                  # restaurar un respaldo
├── programar-backup.command / programar-backup.ps1  # respaldo automático diario
├── .env.example            # plantilla del .env
├── .env                    # variables reales (no se sube a git)
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── core/
│   │   ├── config.py       # DB, JWT, settings
│   │   └── auth.py         # login, tokens, permisos
│   ├── models/
│   │   └── models.py       # tablas SQLAlchemy
│   ├── routers/
│   │   ├── auth.py         # POST /auth/login
│   │   ├── documentos.py   # CRUD + búsqueda
│   │   ├── usuarios.py     # gestión de usuarios
│   │   └── areas.py        # gestión de áreas
│   └── services/
│       └── parser.py       # extracción de texto (PDF/Word/Excel/PPT)
├── db/
│   └── init.sql            # esquema y datos iniciales
├── frontend/
│   └── index.html          # cliente web (lo sirve FastAPI en "/")
└── uploads/                # archivos subidos (volumen Docker)
```

---

## Endpoints principales

| Método | Ruta                  | Descripción                        |
|--------|-----------------------|------------------------------------|
| POST   | /auth/login           | Login, retorna JWT                 |
| GET    | /documentos/          | Buscar y filtrar documentos        |
| POST   | /documentos/          | Subir documento                    |
| DELETE | /documentos/{id}      | Eliminar (solo admin)              |
| GET    | /areas/               | Listar áreas                       |
| POST   | /usuarios/            | Crear usuario (solo admin)         |
| GET    | /usuarios/me          | Perfil del usuario actual          |

---

## Conexión desde otras máquinas

Las demás PCs de la red solo necesitan un navegador.
Apuntan a la IP del servidor:

```
http://192.168.1.X
```

No requieren instalar nada.

---

## Roles

| Rol    | Buscar | Subir | Eliminar | Gestionar usuarios |
|--------|--------|-------|----------|--------------------|
| admin  | ✓      | ✓     | ✓        | ✓                  |
| editor | ✓      | ✓     | ✗        | ✗                  |
| lector | ✓      | ✗     | ✗        | ✗                  |
