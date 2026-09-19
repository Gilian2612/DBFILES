from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.config import get_db
from core.auth import get_current_user, require_admin
from models.models import Area, Usuario

router = APIRouter()

class AreaCreate(BaseModel):
    nombre: str

@router.get("/")
def listar_areas(db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    return db.query(Area).all()

@router.post("/")
def crear_area(data: AreaCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    if db.query(Area).filter(Area.nombre == data.nombre).first():
        raise HTTPException(status_code=400, detail="El área ya existe")
    area = Area(nombre=data.nombre)
    db.add(area)
    db.commit()
    db.refresh(area)
    return area

@router.delete("/{area_id}")
def eliminar_area(area_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    db.delete(area)
    db.commit()
    return {"mensaje": "Área eliminada"}
