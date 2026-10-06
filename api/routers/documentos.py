import os, shutil, uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from core.config import get_db, UPLOAD_DIR, SECRET_KEY, ALGORITHM
from core.auth import get_current_user
from models.models import Documento, Usuario
from services.parser import extraer_texto, detectar_tipo
from jose import jwt, JWTError

router = APIRouter()

# -----------------------------------------------
# Subir documento
# -----------------------------------------------
@router.post("/")
async def subir_documento(
    file: UploadFile = File(...),
    area_id: Optional[int] = None,
    fecha_documento: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if current_user.rol not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Sin permisos para subir documentos")

    tipo = detectar_tipo(file.filename)
    nombre_unico = f"{uuid.uuid4()}_{file.filename}"
    ruta = os.path.join(UPLOAD_DIR, nombre_unico)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(ruta, "wb") as f:
        shutil.copyfileobj(file.file, f)

    contenido = extraer_texto(ruta, tipo)
    tamanio   = os.path.getsize(ruta)

    doc = Documento(
        nombre          = file.filename,
        tipo            = tipo,
        area_id         = area_id,
        ruta            = ruta,
        tamanio_bytes   = tamanio,
        contenido       = contenido,
        subido_por      = current_user.id,
        fecha_documento = fecha_documento,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {"id": doc.id, "nombre": doc.nombre, "tipo": doc.tipo, "tamanio_bytes": doc.tamanio_bytes}

# -----------------------------------------------
# Buscar y filtrar documentos
# -----------------------------------------------
@router.get("/")
def buscar_documentos(
    q:       Optional[str] = Query(None, description="Texto a buscar"),
    tipo:    Optional[str] = Query(None, description="pdf | docx | xlsx | pptx"),
    area_id: Optional[int] = Query(None),
    desde:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    hasta:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    pagina:  int = Query(1, ge=1),
    limite:  int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    offset = (pagina - 1) * limite

    # Construcción dinámica de la query
    condiciones = ["1=1"]
    params = {"limite": limite, "offset": offset}

    if q:
        condiciones.append("d.search_vector @@ plainto_tsquery('spanish', :q)")
        params["q"] = q

    if tipo:
        condiciones.append("d.tipo = :tipo")
        params["tipo"] = tipo

    if area_id:
        condiciones.append("d.area_id = :area_id")
        params["area_id"] = area_id

    if desde:
        condiciones.append("d.fecha_subida >= :desde")
        params["desde"] = desde

    if hasta:
        condiciones.append("d.fecha_subida <= :hasta")
        params["hasta"] = hasta

    where = " AND ".join(condiciones)

    rank_expr = "ts_rank(d.search_vector, plainto_tsquery('spanish', :q)) DESC" if q else "d.fecha_subida DESC"

    sql = text(f"""
        SELECT d.id, d.nombre, d.tipo, d.tamanio_bytes, d.fecha_subida,
               a.nombre AS area, u.nombre AS subido_por
        FROM documentos d
        LEFT JOIN areas    a ON a.id = d.area_id
        LEFT JOIN usuarios u ON u.id = d.subido_por
        WHERE {where}
        ORDER BY {rank_expr}
        LIMIT :limite OFFSET :offset
    """)

    count_sql = text(f"SELECT COUNT(*) FROM documentos d WHERE {where}")

    resultados = db.execute(sql, params).mappings().all()
    total      = db.execute(count_sql, {k: v for k, v in params.items() if k not in ("limite", "offset")}).scalar()

    return {
        "total":    total,
        "pagina":   pagina,
        "limite":   limite,
        "paginas":  -(-total // limite),
        "datos":    [dict(r) for r in resultados]
    }

# -----------------------------------------------
# Detalle de un documento
# -----------------------------------------------
@router.get("/{doc_id}")
def obtener_documento(doc_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    doc = db.query(Documento).filter(Documento.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return doc

# -----------------------------------------------
# Descargar documento
# -----------------------------------------------
@router.get("/{doc_id}/descargar")
def descargar_documento(
    doc_id: int, 
    token: str = Query(...), 
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    user = db.query(Usuario).filter(Usuario.id == int(user_id), Usuario.activo == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autorizado")

    doc = db.query(Documento).filter(Documento.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    if not os.path.exists(doc.ruta):
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado en el servidor")
    return FileResponse(path=doc.ruta, filename=doc.nombre, media_type="application/octet-stream")

# -----------------------------------------------
# Eliminar documento
# -----------------------------------------------
@router.delete("/{doc_id}")
def eliminar_documento(doc_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar")

    doc = db.query(Documento).filter(Documento.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    if os.path.exists(doc.ruta):
        os.remove(doc.ruta)

    db.delete(doc)
    db.commit()
    return {"mensaje": "Documento eliminado"}
