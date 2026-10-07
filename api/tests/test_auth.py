"""
Pruebas para core/auth.py y el endpoint POST /auth/login.
"""
import pytest
import jwt

from core.auth import hash_password, verify_password, create_token
from core.config import SECRET_KEY, ALGORITHM
from tests.conftest import make_user, auth_headers


# ── hash_password / verify_password ──────────────────────────────────────────

def test_hash_es_bcrypt():
    h = hash_password("MiContrasena123")
    assert h.startswith("$2b$")


def test_hash_diferentes_por_salt():
    h1 = hash_password("MiContrasena123")
    h2 = hash_password("MiContrasena123")
    assert h1 != h2


def test_verify_correcto():
    h = hash_password("MiContrasena123")
    assert verify_password("MiContrasena123", h) is True


def test_verify_incorrecto():
    h = hash_password("MiContrasena123")
    assert verify_password("OtraContrasena", h) is False


def test_verify_hash_malformado_no_lanza():
    assert verify_password("cualquier_cosa", "hash_invalido") is False


def test_verify_vacio():
    h = hash_password("MiContrasena123")
    assert verify_password("", h) is False


# ── create_token ──────────────────────────────────────────────────────────────

def test_token_contiene_sub_y_rol():
    token = create_token({"sub": "42", "rol": "admin"})
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "42"
    assert payload["rol"] == "admin"


def test_token_tiene_expiracion():
    token = create_token({"sub": "1"})
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert "exp" in payload


# ── POST /auth/login ──────────────────────────────────────────────────────────

def test_login_exitoso(client, db):
    make_user(db, "u1@test.local", "Clave1234", rol="editor")
    res = client.post("/auth/login", data={"username": "u1@test.local", "password": "Clave1234"})
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["usuario"]["rol"] == "editor"
    assert "password_hash" not in body["usuario"]


def test_login_contrasena_incorrecta(client, db):
    make_user(db, "u2@test.local", "Clave1234")
    res = client.post("/auth/login", data={"username": "u2@test.local", "password": "Mala"})
    assert res.status_code == 401


def test_login_usuario_inexistente(client):
    res = client.post("/auth/login", data={"username": "noexiste@test.local", "password": "cualquier"})
    assert res.status_code == 401


def test_login_usuario_inactivo(client, db):
    make_user(db, "u3@test.local", "Clave1234", activo=False)
    res = client.post("/auth/login", data={"username": "u3@test.local", "password": "Clave1234"})
    assert res.status_code == 401


def test_login_sin_cuerpo(client):
    res = client.post("/auth/login")
    assert res.status_code == 422


# ── tokens inválidos ──────────────────────────────────────────────────────────

def test_token_firmado_con_otra_clave_es_rechazado(client, admin):
    falso = jwt.encode({"sub": str(admin.id)}, "otra_clave_distinta_de_32_bytes_xxxxxx", algorithm=ALGORITHM)
    res = client.get("/usuarios/me", headers={"Authorization": f"Bearer {falso}"})
    assert res.status_code == 401
