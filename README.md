# Gestor Documental Multiusuario

Sistema de gestión y búsqueda documental con servidor central y múltiples clientes.

**Stack:** FastAPI + PostgreSQL + Docker + HTML/JS vanilla

---

## Levantar el proyecto

```bash
# 1. Clonar / copiar los archivos
# 2. Desde la raíz del proyecto:

docker-compose up --build
```

- API:      http://localhost:8000
- Docs API: http://localhost:8000/docs
- Frontend: http://localhost:80

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
├── .env
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
│   └── index.html          # cliente web
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
