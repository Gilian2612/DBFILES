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
