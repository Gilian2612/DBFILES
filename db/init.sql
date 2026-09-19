-- =============================================
-- Gestor Documental Multiusuario
-- Inicialización PostgreSQL
-- =============================================

-- Extensión para búsqueda full-text en español
CREATE EXTENSION IF NOT EXISTS unaccent;

-- -----------------------------------------------
-- Tabla de usuarios
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    rol         VARCHAR(20) NOT NULL DEFAULT 'lector'
                CHECK (rol IN ('admin', 'editor', 'lector')),
    activo      BOOLEAN DEFAULT TRUE,
    creado_en   TIMESTAMP DEFAULT NOW()
);

-- -----------------------------------------------
-- Tabla de áreas / departamentos
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS areas (
    id      SERIAL PRIMARY KEY,
    nombre  TEXT UNIQUE NOT NULL
);

-- -----------------------------------------------
-- Tabla principal de documentos
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS documentos (
    id              SERIAL PRIMARY KEY,
    nombre          TEXT NOT NULL,
    tipo            VARCHAR(10) NOT NULL
                    CHECK (tipo IN ('pdf', 'docx', 'xlsx', 'pptx', 'otro')),
    area_id         INTEGER REFERENCES areas(id) ON DELETE SET NULL,
    ruta            TEXT NOT NULL,
    tamanio_bytes   BIGINT,
    contenido       TEXT,
    search_vector   tsvector GENERATED ALWAYS AS (
                        to_tsvector('spanish', coalesce(nombre, '') || ' ' || coalesce(contenido, ''))
                    ) STORED,
    subido_por      INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    fecha_subida    TIMESTAMP DEFAULT NOW(),
    fecha_documento DATE
);

-- Índice GIN para búsqueda full-text
CREATE INDEX IF NOT EXISTS idx_documentos_search
    ON documentos USING GIN(search_vector);

-- Índices adicionales para filtros comunes
CREATE INDEX IF NOT EXISTS idx_documentos_tipo      ON documentos(tipo);
CREATE INDEX IF NOT EXISTS idx_documentos_area      ON documentos(area_id);
CREATE INDEX IF NOT EXISTS idx_documentos_fecha     ON documentos(fecha_subida);

-- -----------------------------------------------
-- Datos iniciales
-- -----------------------------------------------
INSERT INTO areas (nombre) VALUES
    ('Gerencia'),
    ('Marketing'),
    ('Operaciones'),
    ('Recursos Humanos'),
    ('Tecnología'),
    ('Finanzas')
ON CONFLICT DO NOTHING;

-- Usuario administrador por defecto
-- password: Admin1234  (cambiar en producción)
INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (
    'Administrador',
    'admin@gestor.local',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    'admin'
) ON CONFLICT DO NOTHING;
