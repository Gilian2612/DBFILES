from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from core.config import get_db
from core.auth import verify_password, create_token
from models.models import Usuario

router = APIRouter()

@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(
        Usuario.email == form.username,
        Usuario.activo == True
    ).first()

    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = create_token({"sub": str(user.id), "rol": user.rol})
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {"id": user.id, "nombre": user.nombre, "rol": user.rol}
    }
