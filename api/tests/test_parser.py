"""
Pruebas para services/parser.py.

Las pruebas de extracción de texto crean archivos reales en memoria
usando las mismas bibliotecas que usa el parser (pdfplumber, python-docx,
openpyxl, python-pptx).  Esto evita tener archivos de muestra en el repo
y verifica la integración real.
"""
import io
import os
import tempfile

import pytest

from services.parser import detectar_tipo, extraer_texto


# ── detectar_tipo ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre, esperado", [
    ("informe.pdf",   "pdf"),
    ("INFORME.PDF",   "pdf"),
    ("carta.docx",    "docx"),
    ("carta.doc",     "docx"),
    ("hoja.xlsx",     "xlsx"),
    ("hoja.xls",      "xlsx"),
    ("presentacion.pptx", "pptx"),
    ("presentacion.ppt",  "pptx"),
    ("notas.txt",     "otro"),
    ("imagen.png",    "otro"),
    ("sin_extension", "otro"),
])
def test_detectar_tipo(nombre, esperado):
    assert detectar_tipo(nombre) == esperado


# ── extraer_texto — casos de fallo silencioso ─────────────────────────────────

def test_archivo_inexistente_devuelve_cadena_vacia():
    resultado = extraer_texto("/ruta/que/no/existe.pdf", "pdf")
    assert resultado == ""


def test_tipo_desconocido_devuelve_cadena_vacia():
    resultado = extraer_texto("/cualquier/ruta.txt", "otro")
    assert resultado == ""


def test_archivo_corrupto_devuelve_cadena_vacia():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"esto no es un pdf valido")
        ruta = f.name
    try:
        resultado = extraer_texto(ruta, "pdf")
        assert resultado == ""
    finally:
        os.unlink(ruta)


# ── extraer_texto — archivos reales ──────────────────────────────────────────

def test_extraer_docx():
    from docx import Document
    doc = Document()
    doc.add_paragraph("Hola mundo desde DOCX")
    doc.add_paragraph("Segunda línea")
    buf = io.BytesIO()
    doc.save(buf)
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(buf.getvalue())
        ruta = f.name
    try:
        texto = extraer_texto(ruta, "docx")
        assert "Hola mundo desde DOCX" in texto
        assert "Segunda línea" in texto
    finally:
        os.unlink(ruta)


def test_extraer_xlsx():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "Celda uno"
    ws["B1"] = "Celda dos"
    ws["A2"] = "Fila dos"
    buf = io.BytesIO()
    wb.save(buf)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        f.write(buf.getvalue())
        ruta = f.name
    try:
        texto = extraer_texto(ruta, "xlsx")
        assert "Celda uno" in texto
        assert "Celda dos" in texto
        assert "Fila dos" in texto
    finally:
        os.unlink(ruta)


def test_extraer_pptx():
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    txBox.text_frame.text = "Texto en diapositiva"
    buf = io.BytesIO()
    prs.save(buf)
    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        f.write(buf.getvalue())
        ruta = f.name
    try:
        texto = extraer_texto(ruta, "pptx")
        assert "Texto en diapositiva" in texto
    finally:
        os.unlink(ruta)


def test_docx_sin_parrafos_devuelve_cadena_vacia():
    from docx import Document
    doc = Document()
    buf = io.BytesIO()
    doc.save(buf)
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(buf.getvalue())
        ruta = f.name
    try:
        texto = extraer_texto(ruta, "docx")
        assert texto == ""
    finally:
        os.unlink(ruta)
