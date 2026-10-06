"""
Pruebas para routers/areas.py.
"""
from tests.conftest import make_area, auth_headers


# ── GET /areas/ ───────────────────────────────────────────────────────────────

def test_listar_areas_autenticado(client, db, lector):
    make_area(db, "Finanzas")
    make_area(db, "Legal")
    res = client.get("/areas/", headers=auth_headers(lector))
    assert res.status_code == 200
    nombres = [a["nombre"] for a in res.json()]
    assert "Finanzas" in nombres
    assert "Legal" in nombres


def test_listar_areas_sin_auth(client):
    res = client.get("/areas/")
    assert res.status_code == 401


def test_listar_areas_vacio(client, admin):
    res = client.get("/areas/", headers=auth_headers(admin))
    assert res.status_code == 200
    assert res.json() == []


# ── POST /areas/ ──────────────────────────────────────────────────────────────

def test_crear_area_admin(client, admin):
    res = client.post("/areas/", json={"nombre": "Recursos Humanos"}, headers=auth_headers(admin))
    assert res.status_code == 200
    assert res.json()["nombre"] == "Recursos Humanos"


def test_crear_area_no_admin(client, editor):
    res = client.post("/areas/", json={"nombre": "Marketing"}, headers=auth_headers(editor))
    assert res.status_code == 403


def test_crear_area_duplicada(client, db, admin):
    make_area(db, "Contabilidad")
    res = client.post("/areas/", json={"nombre": "Contabilidad"}, headers=auth_headers(admin))
    assert res.status_code == 400


def test_crear_area_sin_auth(client):
    res = client.post("/areas/", json={"nombre": "Marketing"})
    assert res.status_code == 401


# ── DELETE /areas/:id ─────────────────────────────────────────────────────────

def test_eliminar_area_admin(client, db, admin):
    area = make_area(db, "Archivo")
    res = client.delete(f"/areas/{area.id}", headers=auth_headers(admin))
    assert res.status_code == 200


def test_eliminar_area_no_admin(client, db, lector):
    area = make_area(db, "Secretaria")
    res = client.delete(f"/areas/{area.id}", headers=auth_headers(lector))
    assert res.status_code == 403


def test_eliminar_area_inexistente(client, admin):
    res = client.delete("/areas/99999", headers=auth_headers(admin))
    assert res.status_code == 404
