"""
Pruebas para routers/documentos.py.

Nota: las pruebas de búsqueda de texto completo (parámetro `q`) requieren
PostgreSQL con la columna search_vector y plainto_tsquery. Con SQLite se
marcan como xfail (se espera que fallen en este entorno).
"""
import io
import os
import tempfile
from unittest.mock import patch

import pytest

from models.models import Documento
from tests.conftest import make_area, auth_headers, make_user, SessionTest


def _upload(client, user, filename="doc.pdf", content=b"contenido", area_id=None, fecha=None):
    """Helper para subir un archivo al endpoint."""
    data = {}
    if area_id is not None:
        data["area_id"] = str(area_id)
    if fecha is not None:
        data["fecha_documento"] = fecha
    with patch("routers.documentos.extraer_texto", return_value="texto extraído"):
        res = client.post(
            "/documentos/",
            files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
            data=data,
            headers=auth_headers(user),
        )
    return res


def _make_doc(db, user, area=None, nombre="archivo.pdf", tipo="pdf"):
    """Crea un Documento directamente en la DB con un archivo temporal real."""
    tmp = tempfile.NamedTemporaryFile(suffix=f".{tipo}", delete=False)
    tmp.write(b"contenido de prueba")
    tmp.close()
    doc = Documento(
        nombre=nombre,
        tipo=tipo,
        area_id=area.id if area else None,
        ruta=tmp.name,
        tamanio_bytes=19,
        contenido="contenido de prueba",
        subido_por=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc, tmp.name


# ── POST /documentos/ ─────────────────────────────────────────────────────────

def test_subir_como_editor(client, editor):
    res = _upload(client, editor)
    assert res.status_code == 200
    assert res.json()["nombre"] == "doc.pdf"


def test_subir_como_admin(client, admin):
    res = _upload(client, admin)
    assert res.status_code == 200


def test_subir_como_lector_prohibido(client, lector):
    res = _upload(client, lector)
    assert res.status_code == 403


def test_subir_sin_auth(client):
    with patch("routers.documentos.extraer_texto", return_value=""):
        res = client.post(
            "/documentos/",
            files={"file": ("doc.pdf", io.BytesIO(b"x"), "application/octet-stream")},
        )
    assert res.status_code == 401


def test_subir_area_inexistente(client, editor):
    res = _upload(client, editor, area_id=99999)
    assert res.status_code == 400


def test_subir_con_area_valida(client, db, editor):
    area = make_area(db, "Legal")
    res = _upload(client, editor, area_id=area.id)
    assert res.status_code == 200


def test_subir_con_fecha(client, editor):
    res = _upload(client, editor, fecha="2025-06-15")
    assert res.status_code == 200


def test_middleware_rechaza_content_length_excesivo(client, editor):
    limite_bytes = 100 * 1024 * 1024  # 100 MB
    res = client.post(
        "/documentos/",
        files={"file": ("grande.pdf", io.BytesIO(b"x"), "application/octet-stream")},
        headers={**auth_headers(editor), "Content-Length": str(limite_bytes + 2 * 1024 * 1024)},
    )
    assert res.status_code == 413


# ── GET /documentos/ ──────────────────────────────────────────────────────────

def test_listar_documentos(client, db, lector):
    _make_doc(db, lector, nombre="a.pdf")
    _make_doc(db, lector, nombre="b.docx", tipo="docx")
    res = client.get("/documentos/", headers=auth_headers(lector))
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    assert len(body["datos"]) == 2


def test_listar_sin_auth(client):
    res = client.get("/documentos/")
    assert res.status_code == 401


def test_filtrar_por_tipo(client, db, lector):
    _make_doc(db, lector, nombre="a.pdf",  tipo="pdf")
    _make_doc(db, lector, nombre="b.docx", tipo="docx")
    res = client.get("/documentos/?tipo=pdf", headers=auth_headers(lector))
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["datos"][0]["nombre"] == "a.pdf"


def test_filtrar_por_area(client, db, lector):
    area = make_area(db, "Finanzas")
    _make_doc(db, lector, area=area, nombre="fin.pdf")
    _make_doc(db, lector, nombre="sin_area.pdf")
    res = client.get(f"/documentos/?area_id={area.id}", headers=auth_headers(lector))
    assert res.status_code == 200
    assert res.json()["total"] == 1


def test_paginacion(client, db, lector):
    for i in range(5):
        _make_doc(db, lector, nombre=f"doc{i}.pdf")
    res = client.get("/documentos/?pagina=1&limite=2", headers=auth_headers(lector))
    body = res.json()
    assert body["total"] == 5
    assert len(body["datos"]) == 2
    assert body["paginas"] == 3


@pytest.mark.xfail(reason="plainto_tsquery requiere PostgreSQL")
def test_busqueda_fulltext(client, db, lector):
    res = client.get("/documentos/?q=contrato", headers=auth_headers(lector))
    assert res.status_code == 200


# ── GET /documentos/:id ───────────────────────────────────────────────────────

def test_obtener_documento(client, db, lector):
    doc, ruta = _make_doc(db, lector)
    res = client.get(f"/documentos/{doc.id}", headers=auth_headers(lector))
    assert res.status_code == 200
    os.unlink(ruta)


def test_obtener_documento_inexistente(client, lector):
    res = client.get("/documentos/99999", headers=auth_headers(lector))
    assert res.status_code == 404


# ── DELETE /documentos/:id ────────────────────────────────────────────────────

def test_eliminar_documento_admin(client, db, admin):
    doc, ruta = _make_doc(db, admin)
    res = client.delete(f"/documentos/{doc.id}", headers=auth_headers(admin))
    assert res.status_code == 200
    if os.path.exists(ruta):
        os.unlink(ruta)


def test_eliminar_documento_no_admin(client, db, editor):
    doc, ruta = _make_doc(db, editor)
    res = client.delete(f"/documentos/{doc.id}", headers=auth_headers(editor))
    assert res.status_code == 403
    os.unlink(ruta)


def test_eliminar_documento_inexistente(client, admin):
    res = client.delete("/documentos/99999", headers=auth_headers(admin))
    assert res.status_code == 404


# ── GET /documentos/:id/descargar ─────────────────────────────────────────────

def test_descargar_documento(client, db, lector):
    doc, ruta = _make_doc(db, lector)
    from core.auth import create_token
    token = create_token({"sub": str(lector.id), "rol": lector.rol})
    res = client.get(f"/documentos/{doc.id}/descargar?token={token}")
    assert res.status_code == 200
    os.unlink(ruta)


def test_descargar_token_invalido(client, db, lector):
    doc, ruta = _make_doc(db, lector)
    res = client.get(f"/documentos/{doc.id}/descargar?token=token_invalido")
    assert res.status_code == 401
    os.unlink(ruta)


def test_descargar_archivo_fisico_faltante(client, db, lector):
    doc, ruta = _make_doc(db, lector)
    os.unlink(ruta)  # borrar el archivo físico
    from core.auth import create_token
    token = create_token({"sub": str(lector.id), "rol": lector.rol})
    res = client.get(f"/documentos/{doc.id}/descargar?token={token}")
    assert res.status_code == 404
