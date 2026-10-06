"""
Fixtures compartidos para toda la suite de pruebas.

Antes de importar la app se configuran las variables de entorno para que:
  - FRONTEND_DIR apunte a un directorio temporal (StaticFiles no falla)
  - DATABASE_URL use SQLite en memoria (sin necesidad de PostgreSQL)
  - SECRET_KEY sea un valor fijo conocido
  - UPLOAD_DIR apunte a un directorio temporal
"""
import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Variables de entorno ANTES de importar la app ───────────────────────────

_frontend_tmp = tempfile.mkdtemp()
with open(os.path.join(_frontend_tmp, "index.html"), "w") as _f:
    _f.write("<html><body>test</body></html>")

_upload_tmp = tempfile.mkdtemp()

os.environ.setdefault("FRONTEND_DIR", _frontend_tmp)
os.environ.setdefault("UPLOAD_DIR",   _upload_tmp)
os.environ.setdefault("SECRET_KEY",   "test_secret_key_32bytes_xxxxxxxxxxx")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_USER",     "x")
os.environ.setdefault("POSTGRES_PASSWORD", "x")
os.environ.setdefault("POSTGRES_DB",       "x")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Importar app después de configurar el entorno ───────────────────────────

from core.config import Base, get_db           # noqa: E402
from core.auth import hash_password, create_token  # noqa: E402
from models.models import Usuario, Area, Documento  # noqa: E402
from main import app                           # noqa: E402

# ── Motor SQLite en memoria (StaticPool = una sola conexión compartida) ──────

engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = SessionTest()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_db():
    """Crea las tablas antes de cada prueba y las borra al terminar."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def db(setup_db):
    session = SessionTest()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(setup_db):
    with TestClient(app) as c:
        yield c


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user(db, email, password="Pass1234", rol="lector", nombre=None, activo=True):
    u = Usuario(
        nombre=nombre or email.split("@")[0],
        email=email,
        password_hash=hash_password(password),
        rol=rol,
        activo=activo,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def auth_headers(user):
    token = create_token({"sub": str(user.id), "rol": user.rol})
    return {"Authorization": f"Bearer {token}"}


def make_area(db, nombre="Contabilidad"):
    a = Area(nombre=nombre)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ── Fixtures de usuarios por rol ─────────────────────────────────────────────

@pytest.fixture
def admin(db):
    return make_user(db, "admin@test.local", rol="admin")


@pytest.fixture
def editor(db):
    return make_user(db, "editor@test.local", rol="editor")


@pytest.fixture
def lector(db):
    return make_user(db, "lector@test.local", rol="lector")
