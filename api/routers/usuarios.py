from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from core.config import get_db
from core.auth import get_current_user, require_admin, hash_password, verify_password
from models.models import Usuario

router = APIRouter()

def _safe(u: Usuario) -> dict:
    return {"id": u.id, "nombre": u.nombre, "email": u.email, "rol": u.rol}

class UsuarioCreate(BaseModel):
    nombre:   str
    email:    EmailStr
    password: str
    rol:      str = "lector"

class CambioContrasena(BaseModel):
    contrasena_actual: str
    nueva_contrasena:  str

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
    return _safe(usuario)

@router.get("/")
def listar_usuarios(db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    return [_safe(u) for u in db.query(Usuario).filter(Usuario.activo == True).all()]

@router.get("/me")
def perfil(current_user: Usuario = Depends(get_current_user)):
    return _safe(current_user)

@router.put("/me/contrasena")
def cambiar_contrasena(
    data: CambioContrasena,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not verify_password(data.contrasena_actual, current_user.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta")
    if len(data.nueva_contrasena) < 8:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 8 caracteres")
    current_user.password_hash = hash_password(data.nueva_contrasena)
    db.commit()
    return {"mensaje": "Contraseña actualizada correctamente"}

@router.delete("/{user_id}")
def desactivar_usuario(user_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_admin)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.rol == "admin":
        raise HTTPException(status_code=403, detail="No puedes eliminar a otro administrador")
    user.activo = False
    db.commit()
    return {"mensaje": "Usuario desactivado"}
