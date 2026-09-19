from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from core.config import get_db
from core.auth import get_current_user, require_admin, hash_password
from models.models import Usuario

router = APIRouter()

class UsuarioCreate(BaseModel):
    nombre:   str
    email:    EmailStr
    password: str
    rol:      str = "lector"

@router.post("/")
def crear_usuario(data: UsuarioCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    usuario = Usuario(
        nombre=data.nombre,
        email=data.email,
        password_hash=hash_password(data.password),
        rol=data.rol
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return {"id": usuario.id, "nombre": usuario.nombre, "email": usuario.email, "rol": usuario.rol}

@router.get("/")
def listar_usuarios(db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    return db.query(Usuario).filter(Usuario.activo == True).all()

@router.get("/me")
def perfil(current_user: Usuario = Depends(get_current_user)):
    return {"id": current_user.id, "nombre": current_user.nombre, "email": current_user.email, "rol": current_user.rol}

@router.delete("/{user_id}")
def desactivar_usuario(user_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.activo = False
    db.commit()
    return {"mensaje": "Usuario desactivado"}
