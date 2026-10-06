# Gestor Documental Multiusuario

![CI](https://github.com/Gilian2612/DBFILES/actions/workflows/ci.yml/badge.svg)

**Language / Idioma:** [English](#english) · [Español](#español)

---

# English

Document management and search system with a central server and multiple clients. Users upload office documents (PDF, Word, Excel, PowerPoint) and search them **by their content**, organized by areas and with per-user roles.

**Stack:** FastAPI + PostgreSQL + Docker + vanilla HTML/JS

> Design decisions, rejected alternatives and open items are in [DECISIONS.md](DECISIONS.md#english).

---

## Getting started

Requirement: [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed. Port 80 must be free.

### Automatic setup

- **Mac / Linux:** double-click **`instalar.command`**, or from the Terminal: `./instalar.command`
- **Windows:** right-click **`instalar.ps1`** → *Run with PowerShell*.
  When run as administrator, it also creates the firewall rule for port 80 (private networks only).

The script:
- opens Docker if it is closed;
- creates the `.env` with random passwords, if it does not exist;
- starts the containers;
- waits until the app responds and prints the addresses to use (local, WiFi and Tailscale).

It can be run as many times as needed: it never deletes data or overwrites an existing `.env`.

If macOS blocks it because the project was downloaded as a zip, run this once from the project folder:
`xattr -dr com.apple.quarantine . && chmod +x *.command *.sh`.

### Manual setup (any system)

1. Create the `.env` by copying the example:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and replace `POSTGRES_PASSWORD` and `SECRET_KEY` with long random values, for example with `openssl rand -hex 32`.
   - **Do not change** `POSTGRES_USER` or `POSTGRES_DB`: the backup scripts expect those names.
   - The upload and login limits are optional; see the comments in `.env.example`.
3. Start it:
   ```bash
   docker compose up -d --build
   ```

### Addresses

- App (page + API): http://localhost
- API docs:         http://localhost/docs

> **The database is created only the first time** (from `db/init.sql`). Changing `.env` afterwards does not change the existing database.
> To start from scratch: `docker compose down -v`. **This deletes all data.**

FastAPI serves both the API and the frontend (`frontend/index.html`) on port 80.
The database (5432) is not published outside Docker.

---

## Access from other devices

Other devices only need a browser; nothing to install.

- **Same WiFi:** open the server's IP, e.g. `http://192.168.1.X`
- **Outside the WiFi:** through private [Tailscale](https://tailscale.com). Share the server machine with each remote person from the Tailscale admin panel (*Share*); they install Tailscale and open `http://<server-name>` or `http://100.x.x.x`. Do not enable Tailscale *Funnel* (it makes the app public).

---

## Backups

Each backup stores the database and the uploaded files in `backups/backup_<date>/`.
The last 14 are kept; change the number with `BACKUPS_A_GUARDAR` in `.env`.
Backups work across systems: one made on Windows can be restored on Mac, and vice versa.

| What | Mac / Linux | Windows |
|---|---|---|
| Back up now | `./backup.sh` | double-click `backup.bat` |
| Daily automatic backup (23:00) | double-click `programar-backup.command` | right-click `programar-backup.ps1` → *Run with PowerShell* |
| Another time, e.g. 2:00 | `HORA_BACKUP=2 ./programar-backup.command` | `.\programar-backup.ps1 -Hora 2` |
| Remove the automatic backup | `./programar-backup.command --quitar` | `.\programar-backup.ps1 -Quitar` |
| Restore | `./restaurar.sh` (shows the list) | right-click `restaurar.ps1` → *Run with PowerShell* |

- The automatic backup needs the computer on and Docker Desktop open. If it was off or asleep at that time, it runs as soon as possible. The log is in `logs/backup.log`.
- On Mac, the project **cannot be** in Desktop, Documents or Downloads: macOS does not let scheduled tasks read those folders.
- **Restoring replaces** the current database and files. It asks you to type `SI` to confirm, and first makes a backup of the current state.
- On Linux, the daily backup is scheduled with `cron`; `programar-backup.command` prints the line to add.

---

## Default credentials

| Email               | Password  | Role  |
|---------------------|-----------|-------|
| admin@gestor.local  | Admin1234 | admin |

**For testing only.** There is currently no way to change a password (see [DECISIONS.md](DECISIONS.md#english)); this must be solved before production.

---

## Limits

| Limit | Default | `.env` variable |
|---|---|---|
| File size per upload | 100 MB | `MAX_SUBIDA_MB` (also change it in `frontend/index.html`) |
| Uploads per minute, per user | 25 | `SUBIDAS_POR_MINUTO` |
| Login attempts per minute, per email | 10 | `LOGIN_INTENTOS_POR_MINUTO` |

---

## Roles

| Role   | Search | Upload | Delete | Manage users and areas |
|--------|--------|--------|--------|------------------------|
| admin  | ✓      | ✓      | ✓      | ✓                      |
| editor | ✓      | ✓      | ✗      | ✗                      |
| lector | ✓      | ✗      | ✗      | ✗                      |

There is no screen to manage users or areas yet: an admin does it from `http://<server>/docs` (**Authorize** button, then `POST /usuarios/` or `POST /areas/`).

---

## Main endpoints

| Method | Path                           | Description                        |
|--------|--------------------------------|------------------------------------|
| POST   | /auth/login                    | Log in, returns a JWT              |
| GET    | /documentos/                   | Search and filter documents        |
| POST   | /documentos/                   | Upload a document                  |
| GET    | /documentos/{id}               | Document detail (with extracted text) |
| GET    | /documentos/{id}/descargar     | Download the file                  |
| DELETE | /documentos/{id}               | Delete (admin only)                |
| GET    | /areas/                        | List areas                         |
| POST   | /usuarios/                     | Create a user (admin only)         |
| GET    | /usuarios/me                   | Current user's profile             |
| PUT    | /usuarios/me/contrasena        | Change own password (all users)    |
| GET    | /health                        | Server status                      |

---

## Unit tests

The project uses **pytest-cov** (Coverage.py) for coverage reports. Current coverage: **97%**.

### Run the tests

```bash
# Install test dependencies (once)
docker exec gestor_api pip install pytest httpx pytest-cov -q

# Copy tests into the container
docker cp api/tests gestor_api:/app/tests
docker cp api/pytest.ini gestor_api:/app/pytest.ini

# Run
docker exec gestor_api python -m pytest tests/ -v
```

### Coverage report

```bash
docker exec gestor_api python -m pytest tests/ --cov=. --cov-report=html --cov-report=term-missing
# Copy the HTML report to your machine
docker cp gestor_api:/app/htmlcov ./htmlcov
# Open htmlcov/index.html in your browser
```

### What each file covers

| File | Tests | Covers |
|------|-------|--------|
| `test_auth.py` | 13 | `hash_password`, `verify_password`, JWT creation, login endpoint (200 / 401 / 422 / inactive user) |
| `test_limites.py` | 6 | `LimiteRitmo`: under limit, at limit, window reset, independent keys, thread safety |
| `test_parser.py` | 16 | `detectar_tipo` (all extensions), graceful failure on missing/corrupt files, real DOCX / XLSX / PPTX extraction |
| `test_usuarios.py` | 16 | List (no `password_hash` exposed), password change, create, permission rules on delete |
| `test_areas.py` | 9 | List, create, duplicate (400), delete, auth guards |
| `test_documentos.py` | 25 | Upload (permissions, area validation, 413 middleware), list, filters, pagination, download, delete |

> **Note:** full-text search (`q` parameter) uses PostgreSQL's `plainto_tsquery`. That test is marked `xfail` and is skipped automatically when running against SQLite. It passes when running against the real PostgreSQL container.

---

## Project structure

```
DBFILES/
├── docker-compose.yml
├── instalar.command / instalar.ps1                  # set everything up (Mac-Linux / Windows)
├── backup.sh / backup.ps1 / backup.bat              # back up
├── restaurar.sh / restaurar.ps1                     # restore a backup
├── programar-backup.command / programar-backup.ps1  # daily automatic backup
├── .env.example            # .env template
├── .env                    # real values (not in git)
├── README.md / DECISIONS.md
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-test.txt   # pytest, httpx, pytest-cov
│   ├── pytest.ini
│   ├── main.py             # app, upload size limit, serves the frontend
│   ├── tests/
│   │   ├── conftest.py         # fixtures, SQLite in-memory DB
│   │   ├── test_auth.py
│   │   ├── test_limites.py
│   │   ├── test_parser.py
│   │   ├── test_usuarios.py
│   │   ├── test_areas.py
│   │   └── test_documentos.py
│   ├── core/
│   │   ├── config.py       # DB, JWT, settings and limits
│   │   ├── auth.py         # login, tokens, permissions
│   │   └── limites.py      # rate limits (uploads, login)
│   ├── models/
│   │   └── models.py       # SQLAlchemy tables
│   ├── routers/
│   │   ├── auth.py         # POST /auth/login
│   │   ├── documentos.py   # CRUD + search
│   │   ├── usuarios.py     # user management
│   │   └── areas.py        # area management
│   └── services/
│       └── parser.py       # text extraction (PDF/Word/Excel/PPT)
├── db/
│   └── init.sql            # schema and initial data
├── frontend/
│   └── index.html          # web client (served by FastAPI at "/")
├── uploads/                # uploaded files (not in git)
└── backups/                # backups (not in git)
```

---

# Español

Sistema de gestión y búsqueda documental con servidor central y múltiples clientes. Los usuarios suben documentos de oficina (PDF, Word, Excel, PowerPoint) y los buscan **por su contenido**, organizados por áreas y con roles por usuario.

**Stack:** FastAPI + PostgreSQL + Docker + HTML/JS vanilla

> Las decisiones de diseño, alternativas descartadas y pendientes están en [DECISIONS.md](DECISIONS.md#español) (inglés primero, español después).

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

## Acceso desde otros equipos

Los demás equipos solo necesitan un navegador; no instalan nada.

- **Mismo WiFi:** abrir la IP del servidor, por ejemplo `http://192.168.1.X`
- **Fuera del WiFi:** por [Tailscale](https://tailscale.com) privado. Se comparte la máquina servidor con cada persona remota desde el panel de Tailscale (*Share*); la persona instala Tailscale y abre `http://<nombre-del-servidor>` o `http://100.x.x.x`. No activar *Funnel* de Tailscale (hace pública la app).

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

**Solo para pruebas.** Hoy no hay forma de cambiar una contraseña (ver [DECISIONS.md](DECISIONS.md#español)); hay que resolverlo antes de producción.

---

## Límites

| Límite | Por defecto | Variable del `.env` |
|---|---|---|
| Tamaño por archivo subido | 100 MB | `MAX_SUBIDA_MB` (cambiarlo también en `frontend/index.html`) |
| Subidas por minuto, por usuario | 25 | `SUBIDAS_POR_MINUTO` |
| Intentos de login por minuto, por email | 10 | `LOGIN_INTENTOS_POR_MINUTO` |

---

## Roles

| Rol    | Buscar | Subir | Eliminar | Gestionar usuarios y áreas |
|--------|--------|-------|----------|----------------------------|
| admin  | ✓      | ✓     | ✓        | ✓                          |
| editor | ✓      | ✓     | ✗        | ✗                          |
| lector | ✓      | ✗     | ✗        | ✗                          |

Todavía no hay pantalla para gestionar usuarios ni áreas: un admin lo hace desde `http://<servidor>/docs` (botón **Authorize**, luego `POST /usuarios/` o `POST /areas/`).

---

## Endpoints principales

| Método | Ruta                           | Descripción                        |
|--------|--------------------------------|------------------------------------|
| POST   | /auth/login                    | Login, retorna JWT                 |
| GET    | /documentos/                   | Buscar y filtrar documentos        |
| POST   | /documentos/                   | Subir documento                    |
| GET    | /documentos/{id}               | Detalle del documento (con el texto extraído) |
| GET    | /documentos/{id}/descargar     | Descargar el archivo               |
| DELETE | /documentos/{id}               | Eliminar (solo admin)              |
| GET    | /areas/                        | Listar áreas                       |
| POST   | /usuarios/                     | Crear usuario (solo admin)         |
| GET    | /usuarios/me                   | Perfil del usuario actual          |
| PUT    | /usuarios/me/contrasena        | Cambiar contraseña propia (todos)  |
| GET    | /health                        | Estado del servidor                |

---

## Pruebas unitarias

El proyecto usa **pytest-cov** (Coverage.py) para reportes de cobertura. Cobertura actual: **97%**.

### Correr las pruebas

```bash
# Instalar dependencias de prueba (una sola vez)
docker exec gestor_api pip install pytest httpx pytest-cov -q

# Copiar las pruebas al contenedor
docker cp api/tests gestor_api:/app/tests
docker cp api/pytest.ini gestor_api:/app/pytest.ini

# Ejecutar
docker exec gestor_api python -m pytest tests/ -v
```

### Reporte de cobertura

```bash
docker exec gestor_api python -m pytest tests/ --cov=. --cov-report=html --cov-report=term-missing
# Copiar el reporte al equipo
docker cp gestor_api:/app/htmlcov ./htmlcov
# Abrir htmlcov/index.html en el navegador
```

### Qué cubre cada archivo

| Archivo | Pruebas | Cubre |
|---------|---------|-------|
| `test_auth.py` | 13 | `hash_password`, `verify_password`, creación de JWT, endpoint de login (200 / 401 / 422 / usuario inactivo) |
| `test_limites.py` | 6 | `LimiteRitmo`: bajo el límite, en el límite, expiración de ventana, claves independientes, concurrencia |
| `test_parser.py` | 16 | `detectar_tipo` (todas las extensiones), fallo silencioso con archivos inexistentes o corruptos, extracción real de DOCX / XLSX / PPTX |
| `test_usuarios.py` | 16 | Listado (sin exponer `password_hash`), cambio de contraseña, creación, reglas de permisos para eliminación |
| `test_areas.py` | 9 | Listar, crear, duplicado (400), eliminar, guardias de autenticación |
| `test_documentos.py` | 25 | Subida (permisos, validación de área, middleware 413), listado, filtros, paginación, descarga, eliminación |

> **Nota:** la búsqueda de texto completo (parámetro `q`) usa `plainto_tsquery` de PostgreSQL. Esa prueba está marcada como `xfail` y se omite automáticamente al correr contra SQLite. Pasa cuando se corre contra el contenedor PostgreSQL real.

---

## Estructura

```
DBFILES/
├── docker-compose.yml
├── instalar.command / instalar.ps1                  # levanta todo (Mac-Linux / Windows)
├── backup.sh / backup.ps1 / backup.bat              # respaldo
├── restaurar.sh / restaurar.ps1                     # restaurar un respaldo
├── programar-backup.command / programar-backup.ps1  # respaldo automático diario
├── .env.example            # plantilla del .env
├── .env                    # variables reales (no se sube a git)
├── README.md / DECISIONS.md
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-test.txt   # pytest, httpx, pytest-cov
│   ├── pytest.ini
│   ├── main.py             # app, límite de tamaño de subida, sirve el frontend
│   ├── tests/
│   │   ├── conftest.py         # fixtures, base SQLite en memoria
│   │   ├── test_auth.py
│   │   ├── test_limites.py
│   │   ├── test_parser.py
│   │   ├── test_usuarios.py
│   │   ├── test_areas.py
│   │   └── test_documentos.py
│   ├── core/
│   │   ├── config.py       # DB, JWT, configuración y límites
│   │   ├── auth.py         # login, tokens, permisos
│   │   └── limites.py      # límites de ritmo (subidas, login)
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
├── uploads/                # archivos subidos (no se sube a git)
└── backups/                # respaldos (no se suben a git)
```
