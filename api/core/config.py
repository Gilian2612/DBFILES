import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://gestor_user:gestor_pass_2024@db:5432/gestor_documental")
SECRET_KEY   = os.getenv("SECRET_KEY", "dev_secret_key")
ALGORITHM    = "HS256"
TOKEN_EXPIRE_MINUTES = 480   # 8 horas

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/uploads")

# Límites de subida
MAX_SUBIDA_MB      = int(os.getenv("MAX_SUBIDA_MB", "100"))       # tamaño máximo por archivo
MAX_SUBIDA_BYTES   = MAX_SUBIDA_MB * 1024 * 1024
SUBIDAS_POR_MINUTO = int(os.getenv("SUBIDAS_POR_MINUTO", "25"))   # por usuario

# Límite de intentos de login
LOGIN_INTENTOS_POR_MINUTO = int(os.getenv("LOGIN_INTENTOS_POR_MINUTO", "10"))  # por email

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
