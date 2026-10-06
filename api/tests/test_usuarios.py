"""
Pruebas para routers/usuarios.py.
"""
from tests.conftest import make_user, auth_headers


# ── GET /usuarios/ ────────────────────────────────────────────────────────────

def test_listar_usuarios_admin(client, db, admin):
    make_user(db, "otro@test.local", rol="lector")
    res = client.get("/usuarios/", headers=auth_headers(admin))
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 2
    for u in data:
        assert "password_hash" not in u
        assert "id" in u and "email" in u and "rol" in u


def test_listar_usuarios_no_admin(client, editor):
    res = client.get("/usuarios/", headers=auth_headers(editor))
    assert res.status_code == 403


def test_listar_usuarios_sin_auth(client):
    res = client.get("/usuarios/")
    assert res.status_code == 401


# ── GET /usuarios/me ──────────────────────────────────────────────────────────

def test_perfil_propio(client, lector):
    res = client.get("/usuarios/me", headers=auth_headers(lector))
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "lector@test.local"
    assert "password_hash" not in body


# ── PUT /usuarios/me/contrasena ───────────────────────────────────────────────

def test_cambiar_contrasena_correcto(client, db):
    u = make_user(db, "cambio@test.local", "Antes1234")
    res = client.put(
        "/usuarios/me/contrasena",
        json={"contrasena_actual": "Antes1234", "nueva_contrasena": "Despues1234"},
        headers=auth_headers(u),
    )
    assert res.status_code == 200
    # verificar que ahora puede iniciar sesión con la nueva contraseña
    login = client.post("/auth/login", data={"username": "cambio@test.local", "password": "Despues1234"})
    assert login.status_code == 200


def test_cambiar_contrasena_actual_incorrecta(client, db):
    u = make_user(db, "cambio2@test.local", "Antes1234")
    res = client.put(
        "/usuarios/me/contrasena",
        json={"contrasena_actual": "Incorrecta", "nueva_contrasena": "Despues1234"},
        headers=auth_headers(u),
    )
    assert res.status_code == 400


def test_cambiar_contrasena_nueva_muy_corta(client, db):
    u = make_user(db, "cambio3@test.local", "Antes1234")
    res = client.put(
        "/usuarios/me/contrasena",
        json={"contrasena_actual": "Antes1234", "nueva_contrasena": "corta"},
        headers=auth_headers(u),
    )
    assert res.status_code == 400


def test_cambiar_contrasena_sin_auth(client):
    res = client.put(
        "/usuarios/me/contrasena",
        json={"contrasena_actual": "Antes1234", "nueva_contrasena": "Despues1234"},
    )
    assert res.status_code == 401


# ── POST /usuarios/ ───────────────────────────────────────────────────────────

def test_crear_usuario_admin(client, admin):
    res = client.post(
        "/usuarios/",
        json={"nombre": "Nuevo", "email": "nuevo@example.com", "password": "Nuevo1234", "rol": "lector"},
        headers=auth_headers(admin),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "nuevo@example.com"
    assert "password_hash" not in body


def test_crear_usuario_no_admin(client, editor):
    res = client.post(
        "/usuarios/",
        json={"nombre": "Nuevo", "email": "nuevo2@example.com", "password": "Nuevo1234", "rol": "lector"},
        headers=auth_headers(editor),
    )
    assert res.status_code == 403


def test_crear_usuario_email_duplicado(client, db, admin):
    make_user(db, "dup@example.com")
    res = client.post(
        "/usuarios/",
        json={"nombre": "Dup", "email": "dup@example.com", "password": "Clave1234", "rol": "lector"},
        headers=auth_headers(admin),
    )
    assert res.status_code == 400


# ── DELETE /usuarios/:id ──────────────────────────────────────────────────────

def test_eliminar_lector_como_admin(client, db, admin):
    objetivo = make_user(db, "borrar@test.local", rol="lector")
    res = client.delete(f"/usuarios/{objetivo.id}", headers=auth_headers(admin))
    assert res.status_code == 200


def test_eliminar_editor_como_admin(client, db, admin):
    objetivo = make_user(db, "editor2@test.local", rol="editor")
    res = client.delete(f"/usuarios/{objetivo.id}", headers=auth_headers(admin))
    assert res.status_code == 200


def test_eliminar_admin_bloqueado(client, db, admin):
    otro_admin = make_user(db, "admin2@test.local", rol="admin")
    res = client.delete(f"/usuarios/{otro_admin.id}", headers=auth_headers(admin))
    assert res.status_code == 403


def test_eliminar_cuenta_propia_bloqueado(client, admin):
    res = client.delete(f"/usuarios/{admin.id}", headers=auth_headers(admin))
    assert res.status_code == 400


def test_eliminar_usuario_no_admin(client, db, editor):
    objetivo = make_user(db, "objetivo@test.local", rol="lector")
    res = client.delete(f"/usuarios/{objetivo.id}", headers=auth_headers(editor))
    assert res.status_code == 403


def test_eliminar_usuario_inexistente(client, admin):
    res = client.delete("/usuarios/99999", headers=auth_headers(admin))
    assert res.status_code == 404
