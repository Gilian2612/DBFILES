# Gestor Documental — Decision log / Registro de decisiones

**Language / Idioma:** [English](#english) · [Español](#español)

---

# English

This document records **what was built, why, which alternatives were rejected and what is still open**. Usage instructions are in [README.md](README.md#english).

> **Where each decision comes from.** The decisions in sections 2 to 6 were made before this log existed. Their reasons were **reconstructed from the code and README on `main`**, and are marked *inferred* where nothing was written down. From section 7 (hosting) on, decisions were recorded as they were made. Anything that could not be verified is marked as such.

---

## 1. The problem

A **document management and search system** with one central server and several clients:

- Upload office documents (PDF, Word, Excel, PowerPoint) and **search by their content**, not just by name.
- Organize documents by **areas** (Management, Marketing, Operations, HR, Technology, Finance).
- Several users with **different permissions** depending on their role.
- Clients **install nothing**: they use a browser.
- About **15 people** will use it, some on the server's WiFi and some from outside.

## 2. Base stack

**Decision: FastAPI + PostgreSQL + Docker Compose + vanilla HTML/JS.**

| Piece | Choice | Reason (inferred) |
|---|---|---|
| Backend | FastAPI (Python) | Python has good libraries to read PDF and Office files; FastAPI generates the API docs by itself (`/docs`). |
| Database | PostgreSQL 16 | Built-in full-text search in Spanish, with no separate search engine (see §3). |
| Frontend | A single `index.html`, no frameworks | No build step; anyone can edit it. |
| Deployment | Docker Compose | One command (`docker compose up`) runs everything the same way on Windows or Mac. |

**Rejected (inferred):** a dedicated search engine such as Elasticsearch or Meilisearch. It would be another service to maintain and is not needed for this volume of documents.

## 3. Data model and search

- **Three tables** (`db/init.sql`): `usuarios` (users), `areas` and `documentos` (documents).
- **The text extracted from each file is stored in the database** (`documentos.contenido`). Searching never reopens the files.
- **Full-text search in Spanish**: the `search_vector` column is generated automatically from `name + content` with the `spanish` dictionary, so "contratos" matches "contrato". It has a GIN index to stay fast.
- **Result order**: by relevance (`ts_rank`) when there is a search text; otherwise by upload date, newest first.
- **Filters**: type, area and date range, with pagination of 20 results by default (100 max).
- **Physical files** are stored in `uploads/` with a UUID prefix (`<uuid>_<original name>`), so two files with the same name never overwrite each other.
- **Integrity in the database**: roles and file types are restricted with `CHECK`. Deleting an area or a user leaves its documents without area or author (`ON DELETE SET NULL`), but does not delete them.
- `init.sql` **only runs the first time**, when the PostgreSQL volume is empty. Later schema changes are not applied automatically (see §11).

## 4. Text extraction

`api/services/parser.py` extracts the text on upload:

| Type | Library | What it reads |
|---|---|---|
| PDF | `pdfplumber` | The text of each page |
| Word (`.docx`) | `python-docx` | Paragraphs (**not tables**) |
| Excel (`.xlsx`) | `openpyxl` | Every cell with a value, sheet by sheet |
| PowerPoint (`.pptx`) | `python-pptx` | The text shapes of each slide |
| Others | — | The file is stored, but without text (it does not show up in content searches) |

**If extraction fails, the document is still saved** with empty content and the error goes to the log. Keeping the upload was preferred over losing it.

## 5. Authentication and roles

- **One account per person** (email + password) with **three roles**:

  | Role | Search | Upload | Delete | Manage users and areas |
  |---|---|---|---|---|
  | admin | ✓ | ✓ | ✓ | ✓ |
  | editor | ✓ | ✓ | ✗ | ✗ |
  | lector | ✓ | ✗ | ✗ | ✗ |

- **JWT valid for 8 hours** (one working day), signed with `SECRET_KEY` from `.env`.
- **Passwords with bcrypt.** PR #1 replaced `passlib` with `bcrypt` directly, truncating to 72 bytes, which is bcrypt's limit. Inferred reason: `passlib` is no longer maintained and breaks with recent `bcrypt` versions.
- **Users are deactivated, not deleted** (`activo = false`): who uploaded each document is preserved.
- **A default admin** (`admin@gestor.local` / `Admin1234`) created by `init.sql`. **Its password must be changed before production** (today there is no way to do it, see §11.3).
- With 15 people, individual accounts tell you who uploaded what, and let you remove access for one person without changing everyone's password.

## 6. Download, preview, deletion and backups (PR #1, branch `ft-Garcia`)

- **Download** (`GET /documentos/{id}/descargar`): the token goes in the URL (`?token=...`) because a normal browser download cannot send the `Authorization` header. In exchange, the browser saves the file directly, without loading it entirely into memory with JavaScript.
- **Preview**: shows the **extracted text**, not the formatted document. Enough to confirm it is the right file.
- **Delete (admin only)**: removes the record and the physical file, with a confirmation in the interface.
- **Backups** (`backup.ps1` / `backup.bat`, for Windows): `pg_dump` of the database and a copy of `uploads/` into `backups/backup_<date>/`. They use `docker exec`, so they **do not need the database port to be open**. Reworked later, see §11.4.
- `.gitignore`: `.env`, `uploads/` and `backups/` were excluded so passwords and documents never reach the repository.

## 7. Hosting: a team computer + Tailscale

**Goal:** run the system on one computer, usable both by people on the same WiFi and by people outside.

**Decision: server on our own computer, local access by IP and remote access through private Tailscale.** The same setup already working in the `freewilllawyer-voice` project.

| Option | Pros | Cons |
|---|---|---|
| **Computer + Tailscale (chosen)** | Free; no router ports to open, no public IP or domain; only invited devices get in; traffic is encrypted | Remote people must install Tailscale; the computer must stay on |
| Cloudflare Tunnel or another public tunnel | Public URL with HTTPS, nothing to install | The page is exposed to the internet (with internal documents) |
| Opening router ports | No extra software | Direct exposure, depends on the public IP, needs its own HTTPS |
| Cloud server (VPS) | Does not depend on an office computer | Monthly cost; documents leave our own network |

- **On the same WiFi** Tailscale is not needed: open `http://192.168.1.X`.
- **From outside:** the machine is **shared** (*Share*) with each person's email from the Tailscale admin panel. Each person uses their own free account, so the user limit of our free plan is not reached. *Not verified:* that people the machine is shared with do not count toward that limit. Confirm it in Tailscale's documentation before inviting all 15.
- **Do not enable Tailscale Funnel**: it makes the app public.

## 8. How the browser reaches the API: from nginx to "FastAPI only"

**The problem found:** on `main`, the frontend had `const API = "http://localhost:8000"` hard-coded. `localhost` always means "this same computer", so from any other computer the page loaded but login and everything else failed. It only worked on the server itself.

**Root cause:** nginx served the page (port 80) and the API was a separate program (port 8000). The page needed to know where the API was, and the server's address changes depending on how you connect (local IP, Tailscale IP or name, a tunnel in the future).

Alternatives considered:

| Option | Result |
|---|---|
| Hard-code the server's IP | Rejected: cannot work over WiFi and Tailscale at the same time, and breaks if the IP changes |
| Use the page's address but on port 8000 | Rejected: two open ports and reliance on CORS (set to `allow_origins=["*"]`) |
| nginx as a proxy (`/api` → FastAPI) | Works. Implemented first, then replaced |
| **FastAPI serves both page and API (chosen)** | Works, with one piece less |

**Comparison of the two that work:**

| | nginx + proxy | FastAPI only |
|---|---|---|
| Pieces | 3 containers + nginx config | 2 containers |
| Understanding or fixing it months later | Two places to look for the error | One program and one log |
| Large files and many simultaneous users | Better | Enough for ~15 people |
| Upload size limit | Configured in nginx | Controlled in FastAPI (100 MB, §11.1) |
| Similar to `freewilllawyer-voice` | Different | Same |

**Author's decision: FastAPI only** (branch `feat/ruiz-fastAPI`, commit `d9a6dec`). For ~15 people nginx adds nothing noticeable and is one more piece to maintain.

Changes:

- `api/main.py`: FastAPI serves `frontend/index.html` at `/` (`StaticFiles`, mounted **last** so API routes take priority). The status route moved from `/` to `/health`.
- `frontend/index.html`: `const API = ""`, meaning the API is on the same server that delivered the page.
- `docker-compose.yml`:
  - The `frontend` (nginx) service was removed.
  - The app is published on **port 80** (`80:8000`), so the address has no `:8000`.
  - The frontend is mounted at `/frontend`, read-only.
- **Verified** in an isolated environment with FastAPI 0.111: `/` returns the page, `/documentos/...`, `/docs` and `/health` answer from the API, and an unknown route gives 404. **Pending:** the full test with Docker and the database (login, upload, search, download).

**When to bring nginx back:** if it is published on the internet, if simultaneous users grow a lot, or if very heavy files are handled (video, large scans). It would go in front of FastAPI without changing the frontend.

## 9. Security

- **The database is no longer published outside Docker** (`5432:5432` was removed). Only the API reaches it, through the internal `gestor_net` network.
- **A single exposed port (80).**
- **Development mode removed from the server:** the `./api:/app` mount and `--reload` in the `Dockerfile`. Consequence: after changing API code you must rebuild with `docker compose up -d --build`.
- **Responsibility of whoever deploys:**
  - Use a `.env` with strong passwords and a long random `SECRET_KEY` (`instalar.command` / `instalar.ps1` generate them).
  - Change the default admin password (today there is no way to do it, see §11.3).
  - On a Windows server, allow port 80 in the firewall for the private network only (`instalar.ps1` does it when run as administrator).

## 10. Who decided what

| Decision | Who |
|---|---|
| Stack, data model, roles, text extraction (initial version) | William Santiago Ruiz |
| Download, preview, admin deletion, backups, switch to `bcrypt` (PR #1) | José García (`Joslag`, branch `ft-Garcia`) |
| Host on a computer with local access + Tailscale | William Santiago Ruiz |
| Move from nginx to FastAPI only, on its own branch | William Santiago Ruiz |
| Upload limits (100 MB, 25/min) and login limit (10/min) | William Santiago Ruiz |
| Defer shared access password, 30-day session and default-admin hardening until production | William Santiago Ruiz |
| Installer, automatic backups and restore for both Mac and Windows | William Santiago Ruiz |

## 11. Open items and known limitations

Found while reviewing `main`:

- **Date filters use the upload date**, not the document date.
- **Old formats (`.doc`, `.xls`, `.ppt`)** are accepted, but processed with the libraries for the new formats, which cannot read them. They are stored without text, so they never show up in content searches.
- **Scanned PDFs** (images, no text layer): there is no OCR, so they cannot be found by content.
- **Word tables**: their text is not extracted.
- **There is no screen to manage users or areas.** Today it is done from `http://<server>/docs`. With 15 people it should be in the interface.
- **There is no way to change a password** (see §11.3).
- **Creating a user with an invalid role** gives a 500 error (rejected by the database `CHECK`) instead of a clear message.
- **An upload blocks everyone else while its text is extracted:** `subir_documento` is `async`, but it reads and processes the file with functions that are not. While a large PDF is processed, the server serves nobody else. Fixed by making it a normal function (`def`); the upload rate limiter is already thread-safe. *Inferred from the code, not measured.*
- **The token is lost when the page is reloaded** (kept only in memory), so you have to log in again.
- **The token goes in the download URL**, so it can stay in the browser history. It lasts 8 hours.
- **CORS is still `allow_origins=["*"]`.** No longer needed, since page and API share the same origin. It can be closed.
- **Insecure defaults in `api/core/config.py`:** without a `.env`, the app starts with `SECRET_KEY = "dev_secret_key"` and a fixed database password. It would be better for it not to start without `.env`.
- **No schema migrations:** `alembic` is in `requirements.txt` but unused, and `init.sql` only runs the first time.
- **The `unaccent` extension is installed but unused:** searching "gestion" without the accent may not find "gestión".
- ~~No `.env.example`~~ — resolved in §11.3.
- ~~Backups hard-code `gestor_user` and `gestor_documental`~~ — resolved in §11.4 (they read `.env`).

## 11.1 Fixes and upload limits (branch `feat/ruiz-fastAPI`)

**Fixed: a document's area and date were lost on upload.** The frontend sends them as form fields, but `POST /documentos/` expected them in the URL, so they arrived empty and every document ended up without area or date. They are now read with `Form(...)`. The date is validated as a real date, and a non-existent area returns 400 with a clear message instead of a 500 error.
Documents uploaded before this fix still have no area or date. They must be fixed by hand if needed.

**Fixed: the "Hasta" (to) filter left out that same day.** It now compares against the next day at 00:00 (`fecha_subida < hasta + 1 day`). *Not tested against PostgreSQL* (Docker was not available); it is standard PostgreSQL SQL.

**Size limit: 100 MB per file** (author's decision). Enforced in three layers:

1. **On the page:** warns before sending if the file is bigger, so no time is wasted uploading it.
2. **Early rejection on the server** (`api/main.py`): if the request declares a larger size (plus 1 MB of margin for the other form fields), it is rejected before the file is received.
3. **Exact check** (`api/routers/documentos.py`): bytes are counted while saving. If the limit is exceeded, what was written is deleted and 413 is returned.

**Rate limit: 25 uploads per minute per user** (author's decision). Beyond that, 429 with "Espera un momento" (wait a moment).
- It is **per user**, not global: one person uploading many files does not slow down the other 14.
- **Attempted** uploads count, even if they fail later (size or invalid area).
- Kept **in memory**: it resets when the server restarts, and only works with a single uvicorn process, which is how it runs today.

Both values can be changed in `.env` (`MAX_SUBIDA_MB`, `SUBIDAS_POR_MINUTO`) without touching code. If the size changes, `MAX_SUBIDA_MB` in `frontend/index.html` must change too; it only drives the page's warning.

**Verified** with the real app (FastAPI 0.111, temporary SQLite instead of PostgreSQL, limits reduced to 1 MB and 3 per minute for the test):

| Case | Result |
|---|---|
| Upload with area and date | Stored in the database |
| Non-existent area | 400, "El área seleccionada no existe" |
| File that declares more than the limit | 413 from the early rejection; no file left on disk |
| File just above the limit | 413 from the exact check; what was written is deleted |
| 4 uploads in a row with a limit of 3 per minute | 200, 200, 200, 429 |

## 11.2 Login attempt limit

**10 attempts per minute per email** (author's decision), as in `freewilllawyer-voice`. Beyond that, 429 with "Demasiados intentos de inicio de sesión. Espera un minuto" (too many login attempts, wait a minute). The page shows that message instead of "Credenciales incorrectas" (wrong credentials).

- **Per email, not per IP:** with Docker Desktop (Mac or Windows), the server may see every client with the same internal Docker IP. Counting per IP would make the 15 people share the same 10 attempts.
- **Every attempt counts**, right or wrong. The email is normalized (lowercase, no spaces).
- **Known limitation:** someone trying one password against many different emails is not slowed down by this. For production, a global or per-IP limit could be added, once it is confirmed that the real IP reaches the container.
- It uses the same piece as the upload limit (`api/core/limites.py`, `LimiteRitmo`), in memory and protected with a lock, because login runs on several threads at once. Configured with `LOGIN_INTENTOS_POR_MINUTO` in `.env`.

**Verified** (real app with temporary SQLite):
- 10 failed attempts give 401.
- The 11th gives 429 even with the right password, also when the email is typed in uppercase.
- Another account still logs in normally (200).

**Deferred for this testing stage** (author's decision, to be revisited for production):
- a shared access password like the one in the voice project (it would mean logging in twice, and changing it every time someone leaves);
- remembering the session for 30 days;
- forcing a change of the default admin and refusing to start without `SECRET_KEY`.

## 11.3 Setup: `.env.example` and `instalar.command`

**Problem:** someone cloning the repo and following the README could not start the project, because it was not documented that a `.env` was needed or which variables it holds.

- **`.env.example`:** commented template with the 4 required variables and the 3 optional limits. It warns not to change `POSTGRES_USER` and `POSTGRES_DB`, because backups use them.
- **`instalar.command`** (Mac/Linux, same style as `freewilllawyer-voice`):
  1. Checks Docker and opens it if it is closed.
  2. Creates `.env` with random passwords (`openssl rand`) **only if it does not exist**.
  3. Runs `docker compose up -d --build`.
  4. Waits until `/health` responds.
  5. Prints the addresses: local, WiFi and Tailscale.
  It can be repeated without losing data.
- **Verified:** the script's syntax, the `.env` generation, and that Docker Compose reads it correctly. **Not verified:** a full run, because Docker was not running on the development machine.
- **Windows version:** `instalar.ps1` (see §11.4).
- **Found along the way:** there is no way to change a user's password (neither on the page nor in the API). The default admin stays at `Admin1234`.

## 11.4 Automatic backups, restore and Windows installer

**Author's goal:** the server can be **Mac or Windows**. The app already works the same on both, because it runs in Docker. Only the scripts depend on the system, so there is one version of each per system.

| | Mac / Linux | Windows |
|---|---|---|
| Install | `instalar.command` | `instalar.ps1` |
| Backup | `backup.sh` | `backup.ps1` (+ `backup.bat` as a shortcut) |
| Daily backup | `programar-backup.command` (launchd; on Linux it prints the cron line) | `programar-backup.ps1` (Task Scheduler) |
| Restore | `restaurar.sh` | `restaurar.ps1` |

**Decisions:**
- **Rotation:** the last 14 backups are kept (`BACKUPS_A_GUARDAR`), so a daily backup does not fill the disk.
- **User and database name come from `.env`:** backups no longer hard-code `gestor_user` or `gestor_documental`.
- **On Mac**, files that did not change are hard-linked to the previous backup (`rsync --link-dest`), so 14 backups do not take 14 times the space. **On Windows** they are copied in full: there is no equally simple equivalent.
- **Restore** asks you to type `SI` and first backs up the current state. That safety backup skips rotation, so it never deletes the very backup being restored. It also stops the app while restoring, recreates the database and loads the dump with `ON_ERROR_STOP`. If something fails, it says how to go back to the safety backup.
- **Backups work across systems:** the format is the same, `db_backup.sql` + `uploads/`.
- **Fix in `backup.ps1`:** it used to pass the dump through the PowerShell pipeline (`| Out-File`), which could change the encoding (accents, ñ) and added a BOM at the start. Now the dump is made inside the container and copied with `docker cp`, byte for byte. The restore scripts strip the BOM from old backups.
- **`backup.bat`** became a double-click shortcut that calls `backup.ps1`, so the same logic is not maintained twice.
- **Windows scripts have no accents:** Windows PowerShell 5 misreads accents in files without a BOM.
- **`instalar.ps1`** creates the port 80 firewall rule (private networks only) when run as administrator.

**Verified:**
- Mac, with simulated `docker` and `launchctl` (Docker was not running):
  - the backup creates the dump and the copy of `uploads/`;
  - an unchanged file is hard-linked (same inode);
  - rotation keeps the last N;
  - restore is cancelled without touching anything if `SI` is not typed;
  - restore strips the BOM, replaces `uploads/` and does not delete the restored backup;
  - restore works with the path as an argument from another folder;
  - the scheduler generates a valid plist, rejects invalid hours, and `--quitar` removes it.
- **Not verified:**
  - **none of the Windows scripts has been run** (there was no PowerShell on the development machine; they were only checked to be ASCII);
  - nothing was tested against a real PostgreSQL on any system;
  - whether the firewall rule is enough for access over Tailscale.

## 12. Commit timeline

| Date | Commit | What |
|---|---|---|
| 2026-09-19 | `8457c28` | First upload of the project (inside a `gestor-documental/` folder) |
| 2026-09-19 | `ec3056a`, `7824267` | Project moved to the repository root |
| 2026-09-20 | `ddeb546` | Download, preview, admin deletion, backups, `bcrypt` (branch `ft-Garcia`) |
| 2026-10-06 | `78fdfd1` | PR #1 merged into `main` |
| 2026-10-06 | `d9a6dec` | nginx → FastAPI migration, database closed, no development mode (branch `feat/ruiz-fastAPI`) |
| 2026-10-06 | `1e89bc6` | DECISIONS.md added |
| 2026-10-06 | `952a723` | Area and date fixed on upload, "Hasta" filter; upload and login limits |
| 2026-10-06 | `156ad93` | Installer, automatic backups and restore for Mac and Windows |
| 2026-10-06 | — | README and DECISIONS made bilingual |

## 13. Future decisions

### 13.1 Bringing nginx back
See the end of §8. It would be added as a container in front of FastAPI, with its own upload size limit and timeouts, without touching the frontend.

### 13.2 HTTPS over Tailscale (`tailscale serve`)
Access is plain `http` today. Inside Tailscale the traffic is already encrypted, but `tailscale serve` would give `https://<computer>.<network>.ts.net` with a valid certificate, without changing code. To be evaluated.

### 13.3 If remote access moves to a public tunnel
For example Cloudflare Tunnel. Before that:
- close CORS;
- add a global or per-IP login limit (today it is per email, §11.2);
- make HTTPS mandatory;
- take the token out of the download URL;
- make sure nobody can log in with the default admin.

---

# Español

Este documento registra **qué se construyó, por qué, qué alternativas se descartaron y qué queda pendiente**. Las instrucciones de uso están en [README.md](README.md#español).

> **Sobre el origen de cada decisión.** Las decisiones de las secciones 2 a 6 se tomaron antes de que existiera este registro. Su motivo se **reconstruyó a partir del código y del README de `main`**, y está marcado como *inferido* cuando no quedó escrito en ningún lado. Desde la sección 7 (hosting) las decisiones se documentaron a medida que se tomaban. Lo que no se pudo verificar está marcado como tal.

---

## 1. El problema

Un **sistema de gestión y búsqueda documental** con un servidor central y varios clientes:

- Subir documentos de oficina (PDF, Word, Excel, PowerPoint) y **buscar por su contenido**, no solo por el nombre.
- Organizar los documentos por **áreas** (Gerencia, Marketing, Operaciones, RR. HH., Tecnología, Finanzas).
- Varios usuarios con **permisos distintos** según su rol.
- Los clientes **no instalan nada**: entran con un navegador.
- Lo van a usar **unas 15 personas**, algunas en la misma red WiFi del servidor y otras desde fuera.

## 2. Stack base

**Decisión: FastAPI + PostgreSQL + Docker Compose + HTML/JS sin frameworks.**

| Pieza | Elección | Motivo (inferido) |
|---|---|---|
| Backend | FastAPI (Python) | Python tiene buenas librerías para leer PDF y Office; FastAPI genera la documentación de la API sola (`/docs`). |
| Base de datos | PostgreSQL 16 | Trae búsqueda de texto completo en español sin instalar un motor de búsqueda aparte (ver §3). |
| Frontend | Un solo `index.html` sin frameworks | Sin paso de compilación; cualquiera puede editarlo. |
| Despliegue | Docker Compose | Un comando (`docker compose up`) levanta todo igual en Windows o Mac. |

**Descartado (inferido):** un motor de búsqueda dedicado como Elasticsearch o Meilisearch. Sería otro servicio que mantener y no hace falta con este volumen de documentos.

## 3. Modelo de datos y búsqueda

- **Tres tablas** (`db/init.sql`): `usuarios`, `areas` y `documentos`.
- **El texto extraído de cada archivo se guarda en la base** (`documentos.contenido`). La búsqueda nunca vuelve a abrir los archivos.
- **Búsqueda de texto completo en español**: la columna `search_vector` se genera sola a partir de `nombre + contenido` con el diccionario `spanish`. Así, "contratos" encuentra "contrato". Tiene un índice GIN para que sea rápida.
- **Orden de los resultados**: por relevancia (`ts_rank`) cuando hay texto buscado; si no, por fecha de subida, de la más nueva a la más vieja.
- **Filtros**: tipo, área y rango de fechas, con paginación de 20 resultados por defecto (máximo 100).
- **Los archivos físicos** se guardan en `uploads/` con un prefijo UUID (`<uuid>_<nombre original>`), para que dos archivos con el mismo nombre no se pisen.
- **Integridad en la base**: los roles y los tipos de archivo están restringidos con `CHECK`. Si se borra un área o un usuario, sus documentos quedan sin área o sin autor (`ON DELETE SET NULL`), pero no se borran.
- `init.sql` **solo se ejecuta la primera vez**, cuando el volumen de PostgreSQL está vacío. Los cambios de esquema posteriores no se aplican solos (ver §11).

## 4. Extracción de texto

`api/services/parser.py` extrae el texto al subir el archivo:

| Tipo | Librería | Qué lee |
|---|---|---|
| PDF | `pdfplumber` | El texto de cada página |
| Word (`.docx`) | `python-docx` | Párrafos (las **tablas no**) |
| Excel (`.xlsx`) | `openpyxl` | Todas las celdas con valor, hoja por hoja |
| PowerPoint (`.pptx`) | `python-pptx` | Las formas de texto de cada diapositiva |
| Otros | — | Se guarda el archivo, pero sin texto (no aparece en búsquedas por contenido) |

**Si la extracción falla, el documento se guarda igual** con el contenido vacío y el error queda en el log. Se prefirió no perder la subida.

## 5. Autenticación y roles

- **Una cuenta por persona** (email + contraseña) con **tres roles**:

  | Rol | Buscar | Subir | Eliminar | Gestionar usuarios y áreas |
  |---|---|---|---|---|
  | admin | ✓ | ✓ | ✓ | ✓ |
  | editor | ✓ | ✓ | ✗ | ✗ |
  | lector | ✓ | ✗ | ✗ | ✗ |

- **JWT con 8 horas de validez** (una jornada laboral), firmado con `SECRET_KEY` del `.env`.
- **Contraseñas con bcrypt.** En el PR #1 se reemplazó `passlib` por `bcrypt` directo, recortando a 72 bytes que es el límite de bcrypt. Motivo inferido: `passlib` ya no se mantiene y falla con las versiones nuevas de `bcrypt`.
- **Desactivar en vez de borrar usuarios** (`activo = false`): se conserva quién subió cada documento.
- **Un admin por defecto** (`admin@gestor.local` / `Admin1234`) creado por `init.sql`. **Hay que cambiar esa contraseña antes de producción** (hoy no hay forma de hacerlo, ver §11.3).
- Con 15 personas, tener cuentas individuales sirve para saber quién subió qué y para quitarle el acceso a una sola persona sin cambiarle la clave al resto.

## 6. Descarga, vista previa, borrado y backups (PR #1, rama `ft-Garcia`)

- **Descarga** (`GET /documentos/{id}/descargar`): el token va en la URL (`?token=...`) porque una descarga normal del navegador no puede mandar el encabezado `Authorization`. A cambio, el navegador guarda el archivo directamente, sin cargarlo entero en memoria con JavaScript.
- **Vista previa**: muestra el **texto extraído**, no el documento con su formato. Es suficiente para confirmar que es el archivo correcto.
- **Eliminar (solo admin)**: borra el registro y el archivo físico, con confirmación en la interfaz.
- **Backups** (`backup.ps1` / `backup.bat`, para Windows): `pg_dump` de la base y copia de `uploads/` a `backups/backup_<fecha>/`. Usan `docker exec`, así que **no necesitan que el puerto de la base esté abierto**. Rehechos después, ver §11.4.
- `.gitignore`: se dejaron fuera `.env`, `uploads/` y `backups/` para no subir contraseñas ni documentos al repositorio.

## 7. Hosting: un PC del equipo + Tailscale

**Objetivo:** que el sistema corra en un PC y lo usen tanto quienes están en el mismo WiFi como quienes están fuera.

**Decisión: servidor en un PC propio, acceso local por IP y acceso remoto por Tailscale privado.** Es la misma forma que ya funciona en el proyecto `freewilllawyer-voice`.

| Opción | Ventajas | Desventajas |
|---|---|---|
| **PC + Tailscale (elegida)** | Gratis; no hay que abrir puertos en el router ni tener IP pública o dominio; solo entran los dispositivos invitados; el tráfico va cifrado | Quien entra desde fuera tiene que instalar Tailscale; el PC debe quedar encendido |
| Cloudflare Tunnel u otro túnel público | URL pública con HTTPS, sin instalar nada | La página queda expuesta a internet (con documentos internos) |
| Abrir puertos en el router | Sin software extra | Exposición directa, depende de la IP pública, requiere HTTPS propio |
| Servidor en la nube (VPS) | No depende de un PC de la oficina | Costo mensual; los documentos salen de la red propia |

- **En el mismo WiFi** no hace falta Tailscale: se entra por `http://192.168.1.X`.
- **Desde fuera:** se **comparte la máquina** (*Share*) con el correo de cada persona, desde el panel de Tailscale. Cada una usa su propia cuenta gratuita, así no se llega al límite de usuarios del plan gratuito de la red propia. *Sin verificar:* que las personas con las que se comparte no cuentan para ese límite. Hay que confirmarlo en la documentación de Tailscale antes de invitar a las 15.
- **No activar Tailscale Funnel**, porque hace pública la app.

## 8. Cómo llega el navegador a la API: de nginx a "solo FastAPI"

**El problema encontrado:** en `main`, el frontend tenía fijo `const API = "http://localhost:8000"`. `localhost` es siempre "este mismo equipo", así que desde cualquier otro PC la página cargaba pero el login y todo lo demás fallaban. Solo funcionaba en el propio servidor.

**Causa de fondo:** la página la entregaba nginx (puerto 80) y la API era otro programa (puerto 8000). La página necesitaba saber dónde estaba la API, y la dirección del servidor cambia según cómo se entra (IP local, IP o nombre de Tailscale, un túnel en el futuro).

Alternativas evaluadas:

| Opción | Resultado |
|---|---|
| Escribir a mano la IP del servidor | Descartada: no sirve a la vez por WiFi y por Tailscale, y se rompe si cambia la IP |
| Usar la dirección de la página pero en el puerto 8000 | Descartada: dos puertos abiertos y dependencia de CORS (que está en `allow_origins=["*"]`) |
| nginx como proxy (`/api` → FastAPI) | Funciona. Se implementó primero y luego se reemplazó |
| **Solo FastAPI entrega página y API (elegida)** | Funciona, con una pieza menos |

**Comparación de las dos que funcionan:**

| | nginx + proxy | Solo FastAPI |
|---|---|---|
| Piezas | 3 contenedores + configuración de nginx | 2 contenedores |
| Entenderlo o arreglarlo meses después | Dos lugares donde buscar el error | Un solo programa y un solo log |
| Archivos grandes y muchos usuarios a la vez | Mejor | Suficiente para ~15 personas |
| Límite de tamaño de subida | Configurable en nginx | Controlado en FastAPI (100 MB, §11.1) |
| Parecido con `freewilllawyer-voice` | Distinto | Igual |

**Decisión del autor: solo FastAPI** (rama `feat/ruiz-fastAPI`, commit `d9a6dec`). Para ~15 personas, nginx no aporta nada que se note y agrega una pieza más que mantener.

Cambios:

- `api/main.py`: FastAPI entrega `frontend/index.html` en `/` (`StaticFiles`, montado **al final** para que las rutas de la API tengan prioridad). La ruta de estado pasó de `/` a `/health`.
- `frontend/index.html`: `const API = ""`, o sea, la API está en el mismo servidor que entregó la página.
- `docker-compose.yml`:
  - Se eliminó el servicio `frontend` (nginx).
  - La app se publica en el **puerto 80** (`80:8000`), así la dirección queda sin `:8000`.
  - El frontend se monta en `/frontend`, en modo solo lectura.
- **Verificado** en un entorno aislado con FastAPI 0.111: `/` devuelve la página, `/documentos/...`, `/docs` y `/health` responden la API, y una ruta inexistente da 404. **Pendiente:** la prueba completa con Docker y la base de datos (login, subir, buscar, descargar).

**Cuándo volver a poner nginx:** si se publica en internet, si crecen mucho los usuarios simultáneos o si se manejan archivos muy pesados (video, escaneos grandes). Se pondría delante de FastAPI sin cambiar el frontend.

## 9. Seguridad

- **La base de datos ya no se publica fuera de Docker** (se quitó `5432:5432`). Solo la API la alcanza, por la red interna `gestor_net`.
- **Un solo puerto expuesto (80).**
- **Se quitó el modo desarrollo en el servidor:** el montaje `./api:/app` y `--reload` del `Dockerfile`. Consecuencia: después de cambiar código de la API hay que reconstruir con `docker compose up -d --build`.
- **Responsabilidad de quien despliega:**
  - Usar un `.env` con contraseñas fuertes y un `SECRET_KEY` largo y aleatorio (`instalar.command` / `instalar.ps1` los generan).
  - Cambiar la contraseña del admin por defecto (hoy no hay forma de hacerlo, ver §11.3).
  - Si el servidor es Windows, permitir el puerto 80 en el firewall solo para la red privada (`instalar.ps1` lo hace si se ejecuta como administrador).

## 10. Quién decidió qué

| Decisión | Quién |
|---|---|
| Stack, modelo de datos, roles, extracción de texto (versión inicial) | William Santiago Ruiz |
| Descarga, vista previa, borrado por admin, backups, cambio a `bcrypt` (PR #1) | José García (`Joslag`, rama `ft-Garcia`) |
| Hostear en un PC con acceso local + Tailscale | William Santiago Ruiz |
| Pasar de nginx a solo FastAPI, en una rama propia | William Santiago Ruiz |
| Límites de subida (100 MB, 25/min) y de login (10/min) | William Santiago Ruiz |
| Dejar para producción la clave general, la sesión de 30 días y el endurecimiento del admin por defecto | William Santiago Ruiz |
| Instalador, respaldos automáticos y restauración para Mac y Windows | William Santiago Ruiz |

## 11. Pendientes y limitaciones conocidas

Encontradas al revisar `main`:

- **Los filtros de fecha usan la fecha de subida**, no la fecha del documento.
- **Formatos viejos (`.doc`, `.xls`, `.ppt`)** se aceptan, pero se procesan con las librerías de los formatos nuevos, que no los leen. Se guardan sin texto, así que no aparecen en búsquedas por contenido.
- **PDFs escaneados** (imagen, sin capa de texto): no hay OCR, así que no se encuentran por contenido.
- **Tablas de Word**: su texto no se extrae.
- **No hay pantalla para gestionar usuarios ni áreas.** Hoy se hace desde `http://<servidor>/docs`. Con 15 personas conviene tenerla en la interfaz.
- **No hay forma de cambiar una contraseña** (ver §11.3).
- **Crear un usuario con un rol inválido** da un error 500 (lo rechaza el `CHECK` de la base) en vez de un mensaje claro.
- **Subir un archivo bloquea al resto mientras se extrae el texto:** `subir_documento` es `async`, pero lee el archivo y lo procesa con funciones que no lo son. Mientras se procesa un PDF grande, el servidor no atiende a nadie más. Se arregla convirtiéndolo en función normal (`def`); el control de ritmo de subidas ya está protegido para varios hilos. *Deducido del código, no medido.*
- **El token se pierde al recargar la página** (se guarda solo en memoria), así que hay que volver a iniciar sesión.
- **El token va en la URL de descarga**, por lo que puede quedar en el historial del navegador. Dura 8 horas.
- **CORS sigue en `allow_origins=["*"]`.** Ya no hace falta, porque página y API comparten origen. Se puede cerrar.
- **Valores por defecto inseguros en `api/core/config.py`:** si falta el `.env`, la app arranca con `SECRET_KEY = "dev_secret_key"` y una contraseña de base fija. Sería mejor que no arranque sin `.env`.
- **No hay migraciones de esquema:** `alembic` está en `requirements.txt`, pero no se usa, e `init.sql` solo corre la primera vez.
- **La extensión `unaccent` se instala pero no se usa:** buscar "gestion" sin tilde puede no encontrar "gestión".
- ~~No hay `.env.example`~~ — resuelto en §11.3.
- ~~Los backups tienen fijos `gestor_user` y `gestor_documental`~~ — resuelto en §11.4 (ahora leen el `.env`).

## 11.1 Arreglos y límites de subida (rama `feat/ruiz-fastAPI`)

**Arreglado: el área y la fecha del documento se perdían al subir.** El frontend los manda como campos del formulario, pero `POST /documentos/` los esperaba en la URL, así que llegaban vacíos y todos los documentos quedaban sin área ni fecha. Ahora se leen con `Form(...)`. La fecha se valida como fecha real, y si el área no existe se responde 400 con un mensaje claro en vez de un error 500.
Los documentos que se subieron antes de este arreglo siguen sin área ni fecha. Hay que corregirlos a mano si se necesitan.

**Arreglado: el filtro "Hasta" dejaba fuera ese mismo día.** Ahora compara contra el día siguiente a las 00:00 (`fecha_subida < hasta + 1 día`). *No probado contra PostgreSQL* (Docker no estaba disponible); es SQL estándar de PostgreSQL.

**Límite de tamaño: 100 MB por archivo** (decisión del autor). Se controla en tres capas:

1. **En la página:** avisa antes de enviar si el archivo pesa más, para no gastar tiempo subiéndolo.
2. **Rechazo temprano en el servidor** (`api/main.py`): si la petición declara un tamaño mayor (más 1 MB de margen para los demás campos del formulario), se rechaza antes de recibir el archivo.
3. **Control exacto** (`api/routers/documentos.py`): al guardar se van contando los bytes. Si se pasa del límite, se borra lo escrito y se responde 413.

**Límite de ritmo: 25 subidas por minuto por usuario** (decisión del autor). Si se pasa, responde 429 con "Espera un momento".
- Es **por usuario**, no global: una persona subiendo muchos archivos no frena a las otras 14.
- Se cuentan las subidas **intentadas**, aunque fallen después (por tamaño o por área inválida).
- Se guarda **en memoria**: se reinicia al reiniciar el servidor, y solo funciona con un único proceso de uvicorn, que es como corre hoy.

Los dos valores se pueden cambiar en el `.env` (`MAX_SUBIDA_MB`, `SUBIDAS_POR_MINUTO`) sin tocar el código. Si se cambia el tamaño, hay que cambiar también `MAX_SUBIDA_MB` en `frontend/index.html`, que es solo el aviso de la página.

**Verificado** con la app real (FastAPI 0.111, SQLite temporal en lugar de PostgreSQL y límites reducidos a 1 MB y 3 por minuto para la prueba):

| Caso | Resultado |
|---|---|
| Subir con área y fecha | Se guardan en la base |
| Área inexistente | 400, "El área seleccionada no existe" |
| Archivo que declara más del límite | 413 por el rechazo temprano; no queda archivo en disco |
| Archivo apenas por encima del límite | 413 por el control exacto; se borra lo escrito |
| 4 subidas seguidas con límite 3 por minuto | 200, 200, 200, 429 |

## 11.2 Límite de intentos de login

**10 intentos por minuto por email** (decisión del autor), igual que en `freewilllawyer-voice`. Se pasa a 429 con "Demasiados intentos de inicio de sesión. Espera un minuto". La página muestra ese mensaje en vez de "Credenciales incorrectas".

- **Por email y no por IP:** con Docker Desktop (Mac o Windows), el servidor puede ver a todos los clientes con la misma IP interna de Docker. Si se contara por IP, las 15 personas compartirían los mismos 10 intentos.
- **Cuenta todos los intentos**, correctos o no. El email se normaliza (minúsculas, sin espacios).
- **Limitación conocida:** alguien que pruebe una sola contraseña contra muchos emails distintos no se frena con esto. Para producción se podría sumar un límite global o por IP, si se confirma que la IP real llega al contenedor.
- Usa la misma pieza que el límite de subidas (`api/core/limites.py`, `LimiteRitmo`), en memoria y protegida con un candado (lock), porque el login corre en varios hilos a la vez. Se configura con `LOGIN_INTENTOS_POR_MINUTO` en el `.env`.

**Verificado** (app real con SQLite temporal):
- 10 intentos fallidos dan 401.
- El 11.º da 429 aunque la clave sea correcta, también escribiendo el email en mayúsculas.
- Otra cuenta sigue entrando normal (200).

**Descartado para esta etapa de pruebas** (decisión del autor, se revisará para producción):
- una clave general de acceso como la del voice (sería doble login, y hay que cambiarla cada vez que alguien se va);
- recordar la sesión 30 días;
- obligar a cambiar el admin por defecto y no arrancar sin `SECRET_KEY`.

## 11.3 Instalación: `.env.example` e `instalar.command`

**Problema:** quien clonaba el repo y seguía el README no podía levantar el proyecto, porque no estaba documentado que hacía falta un `.env` ni qué variables lleva.

- **`.env.example`:** plantilla comentada con las 4 variables obligatorias y los 3 límites opcionales. Advierte que `POSTGRES_USER` y `POSTGRES_DB` no se deben cambiar, porque los backups los usan.
- **`instalar.command`** (Mac/Linux, mismo estilo que `freewilllawyer-voice`):
  1. Comprueba Docker y lo abre si está cerrado.
  2. Crea el `.env` con contraseñas aleatorias (`openssl rand`) **solo si no existe**.
  3. Corre `docker compose up -d --build`.
  4. Espera a que `/health` responda.
  5. Muestra las direcciones: local, WiFi y Tailscale.
  Se puede repetir sin perder datos.
- **Verificado:** la sintaxis del script, la generación del `.env` y que Docker Compose lo lee bien. **Sin verificar:** la ejecución completa, porque Docker no estaba corriendo en el equipo de desarrollo.
- **Versión para Windows:** `instalar.ps1` (ver §11.4).
- **Encontrado al hacerlo:** no existe ninguna forma de cambiar la contraseña de un usuario (ni en la página ni en la API). El admin por defecto queda con `Admin1234`.

## 11.4 Respaldos automáticos, restauración e instalador para Windows

**Objetivo del autor:** que el servidor pueda ser **Mac o Windows**. La app ya funciona igual en los dos, porque corre en Docker. Lo que depende del sistema son los scripts, así que hay una versión de cada uno por sistema.

| | Mac / Linux | Windows |
|---|---|---|
| Instalar | `instalar.command` | `instalar.ps1` |
| Respaldo | `backup.sh` | `backup.ps1` (+ `backup.bat` como atajo) |
| Respaldo diario | `programar-backup.command` (launchd; en Linux muestra la línea de cron) | `programar-backup.ps1` (Programador de tareas) |
| Restaurar | `restaurar.sh` | `restaurar.ps1` |

**Decisiones:**
- **Rotación:** se conservan los últimos 14 respaldos (`BACKUPS_A_GUARDAR`), para que un respaldo diario no llene el disco.
- **Usuario y base desde el `.env`:** los respaldos ya no tienen fijos `gestor_user` ni `gestor_documental`.
- **En Mac**, los archivos que no cambiaron se enlazan al respaldo anterior (`rsync --link-dest`), así 14 respaldos no ocupan 14 veces lo mismo. **En Windows** se copian completos: no hay una herramienta equivalente igual de simple.
- **Restaurar** pide escribir `SI` y antes hace un respaldo del estado actual. Ese respaldo de seguridad no rota, para no borrar justo el que se va a restaurar. Además, detiene la app mientras restaura, recrea la base y carga el volcado con `ON_ERROR_STOP`. Si algo falla, indica cómo volver al respaldo de seguridad.
- **Respaldos compatibles entre sistemas:** el formato es el mismo, `db_backup.sql` + `uploads/`.
- **Arreglo en `backup.ps1`:** antes pasaba el volcado por la tubería de PowerShell (`| Out-File`). Eso podía cambiar la codificación (tildes, ñ) y agregaba un BOM al principio. Ahora el volcado se hace dentro del contenedor y se copia con `docker cp`, byte a byte. Los restauradores quitan el BOM de los respaldos viejos.
- **`backup.bat`** pasó a ser un atajo de doble clic que llama a `backup.ps1`, para no mantener dos copias de la misma lógica.
- **Scripts de Windows sin tildes:** Windows PowerShell 5 lee mal los acentos en archivos sin BOM.
- **`instalar.ps1`** crea la regla de firewall del puerto 80 (solo redes privadas) si se ejecuta como administrador.

**Verificado:**
- Mac, con un `docker` y un `launchctl` simulados (Docker no estaba corriendo):
  - el respaldo genera el volcado y la copia de `uploads/`;
  - el archivo que no cambió queda enlazado (mismo inodo);
  - la rotación deja los últimos N;
  - restaurar se cancela sin tocar nada si no se escribe `SI`;
  - restaurar quita el BOM, reemplaza `uploads/` y no borra el respaldo restaurado;
  - restaurar funciona con la ruta como argumento desde otra carpeta;
  - el programador genera un plist válido, rechaza horas inválidas y `--quitar` lo elimina.
- **Sin verificar:**
  - **ningún script de Windows se ejecutó** (no había PowerShell en el equipo de desarrollo; solo se revisó que fueran ASCII);
  - en ningún sistema se probó contra PostgreSQL real;
  - no se probó que la regla de firewall alcance para el acceso por Tailscale.

## 12. Cronología (commits)

| Fecha | Commit | Qué |
|---|---|---|
| 2026-09-19 | `8457c28` | Primera subida del proyecto (dentro de una carpeta `gestor-documental/`) |
| 2026-09-19 | `ec3056a`, `7824267` | Se movió el proyecto a la raíz del repositorio |
| 2026-09-20 | `ddeb546` | Descarga, vista previa, borrado por admin, backups, `bcrypt` (rama `ft-Garcia`) |
| 2026-10-06 | `78fdfd1` | Merge del PR #1 a `main` |
| 2026-10-06 | `d9a6dec` | Migración de nginx a FastAPI, base de datos cerrada, sin modo desarrollo (rama `feat/ruiz-fastAPI`) |
| 2026-10-06 | `1e89bc6` | Se agregó DECISIONS.md |
| 2026-10-06 | `952a723` | Área y fecha al subir, filtro "Hasta"; límites de subida y de login |
| 2026-10-06 | `156ad93` | Instalador, respaldos automáticos y restauración para Mac y Windows |
| 2026-10-06 | — | README y DECISIONS bilingües |

## 13. Decisiones a futuro

### 13.1 Volver a poner nginx
Ver el final de §8. Se agregaría como contenedor delante de FastAPI, con su propio límite de tamaño de subida y tiempos de espera, sin tocar el frontend.

### 13.2 HTTPS sobre Tailscale (`tailscale serve`)
Hoy el acceso es `http` simple. Dentro de Tailscale el tráfico ya va cifrado, pero `tailscale serve` daría `https://<pc>.<red>.ts.net` con certificado válido, sin cambiar el código. Pendiente de evaluar.

### 13.3 Si el acceso remoto pasa a un túnel público
Por ejemplo, Cloudflare Tunnel. Antes habría que:
- cerrar CORS;
- sumar un límite de login global o por IP (hoy es por email, §11.2);
- tener HTTPS obligatorio;
- sacar el token de la URL de descarga;
- revisar que no se pueda iniciar sesión con el admin por defecto.
