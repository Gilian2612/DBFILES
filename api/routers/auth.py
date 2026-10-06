from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from core.config import get_db, LOGIN_INTENTOS_POR_MINUTO
from core.auth import verify_password, create_token
from core.limites import LimiteRitmo
from models.models import Usuario

router = APIRouter()

# Por email y no por IP: con Docker Desktop todos los clientes pueden llegar con la misma IP interna
limite_login = LimiteRitmo(
    LOGIN_INTENTOS_POR_MINUTO, 60,
    "Demasiados intentos de inicio de sesión. Espera un minuto e inténtalo de nuevo.",
)

@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    limite_login.registrar(form.username.strip().lower())

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
