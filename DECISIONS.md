# Gestor Documental — Registro de decisiones

Este documento registra **qué se construyó, por qué, qué alternativas se descartaron y qué queda pendiente**. Las instrucciones de uso están en [README.md](README.md).

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
- **Un admin por defecto** (`admin@gestor.local` / `Admin1234`) creado por `init.sql`. **Hay que cambiar esa contraseña al desplegar.**
- Con 15 personas, tener cuentas individuales sirve para saber quién subió qué y para quitarle el acceso a una sola persona sin cambiarle la clave al resto.

## 6. Descarga, vista previa, borrado y backups (PR #1, rama `ft-Garcia`)

- **Descarga** (`GET /documentos/{id}/descargar`): el token va en la URL (`?token=...`) porque una descarga normal del navegador no puede mandar el encabezado `Authorization`. A cambio, el navegador guarda el archivo directamente, sin cargarlo entero en memoria con JavaScript.
- **Vista previa**: muestra el **texto extraído**, no el documento con su formato. Es suficiente para confirmar que es el archivo correcto.
- **Eliminar (solo admin)**: borra el registro y el archivo físico, con confirmación en la interfaz.
- **Backups** (`backup.ps1` / `backup.bat`, para Windows): `pg_dump` de la base y copia de `uploads/` a `backups/backup_<fecha>/`. Usan `docker exec`, así que **no necesitan que el puerto de la base esté abierto**.
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
| Límite de tamaño de subida | Configurable en nginx | No hay (ver §11) |
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
  - Crear un `.env` con contraseñas fuertes y un `SECRET_KEY` largo y aleatorio.
  - Cambiar la contraseña del admin por defecto.
  - Si el servidor es Windows, permitir el puerto 80 en el firewall solo para la red privada.

## 10. Quién decidió qué

| Decisión | Quién |
|---|---|
| Stack, modelo de datos, roles, extracción de texto (versión inicial) | William Santiago Ruiz |
| Descarga, vista previa, borrado por admin, backups, cambio a `bcrypt` (PR #1) | José García (`Joslag`, rama `ft-Garcia`) |
| Hostear en un PC con acceso local + Tailscale | William Santiago Ruiz |
| Pasar de nginx a solo FastAPI, en una rama propia | William Santiago Ruiz |

## 11. Pendientes y limitaciones conocidas

Encontradas al revisar `main`:

- **Los filtros de fecha usan la fecha de subida**, no la fecha del documento.
- **Formatos viejos (`.doc`, `.xls`, `.ppt`)** se aceptan, pero se procesan con las librerías de los formatos nuevos, que no los leen. Se guardan sin texto, así que no aparecen en búsquedas por contenido.
- **PDFs escaneados** (imagen, sin capa de texto): no hay OCR, así que no se encuentran por contenido.
- **Tablas de Word**: su texto no se extrae.
- **No hay pantalla para gestionar usuarios ni áreas.** Hoy se hace desde `http://<servidor>/docs`. Con 15 personas conviene tenerla en la interfaz.
- **Crear un usuario con un rol inválido** da un error 500 (lo rechaza el `CHECK` de la base) en vez de un mensaje claro.
- **Subir un archivo bloquea al resto mientras se extrae el texto:** `subir_documento` es `async`, pero lee el archivo y lo procesa con funciones que no lo son. Mientras se procesa un PDF grande, el servidor no atiende a nadie más. Se arregla convirtiéndolo en función normal (`def`), y en ese caso el control de ritmo necesitaría un candado (lock). *Deducido del código, no medido.*
- **El token se pierde al recargar la página** (se guarda solo en memoria), así que hay que volver a iniciar sesión.
- **El token va en la URL de descarga**, por lo que puede quedar en el historial del navegador. Dura 8 horas.
- **CORS sigue en `allow_origins=["*"]`.** Ya no hace falta, porque página y API comparten origen. Se puede cerrar.
- **Valores por defecto inseguros en `api/core/config.py`:** si falta el `.env`, la app arranca con `SECRET_KEY = "dev_secret_key"` y una contraseña de base fija. Sería mejor que no arranque sin `.env`.
- **No hay `.env.example`.** El README menciona el `.env` pero no dice qué variables lleva (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `SECRET_KEY`).
- **Los backups tienen fijos `gestor_user` y `gestor_documental`.** Si el `.env` usa otros nombres, el backup falla.
- **No hay migraciones de esquema:** `alembic` está en `requirements.txt`, pero no se usa, e `init.sql` solo corre la primera vez.
- **La extensión `unaccent` se instala pero no se usa:** buscar "gestion" sin tilde puede no encontrar "gestión".

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

## 13. Decisiones a futuro

### 13.1 Volver a poner nginx
Ver el final de §8. Se agregaría como contenedor delante de FastAPI, con su propio límite de tamaño de subida y tiempos de espera, sin tocar el frontend.

### 13.2 HTTPS sobre Tailscale (`tailscale serve`)
Hoy el acceso es `http` simple. Dentro de Tailscale el tráfico ya va cifrado, pero `tailscale serve` daría `https://<pc>.<red>.ts.net` con certificado válido, sin cambiar el código. Pendiente de evaluar.

### 13.3 Si el acceso remoto pasa a un túnel público
Por ejemplo, Cloudflare Tunnel. Antes habría que:
- cerrar CORS;
- poner un límite de intentos de login;
- tener HTTPS obligatorio;
- sacar el token de la URL de descarga;
- revisar que no se pueda iniciar sesión con el admin por defecto.
