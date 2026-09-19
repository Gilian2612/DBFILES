from sqlalchemy import Column, Integer, String, Text, Boolean, BigInteger, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from core.config import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id            = Column(Integer, primary_key=True, index=True)
    nombre        = Column(Text, nullable=False)
    email         = Column(String, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    rol           = Column(String(20), default="lector")
    activo        = Column(Boolean, default=True)
    creado_en     = Column(DateTime, default=datetime.utcnow)

    documentos = relationship("Documento", back_populates="subido_por_rel")

class Area(Base):
    __tablename__ = "areas"

    id     = Column(Integer, primary_key=True, index=True)
    nombre = Column(Text, unique=True, nullable=False)

    documentos = relationship("Documento", back_populates="area_rel")

class Documento(Base):
    __tablename__ = "documentos"

    id              = Column(Integer, primary_key=True, index=True)
    nombre          = Column(Text, nullable=False)
    tipo            = Column(String(10), nullable=False)
    area_id         = Column(Integer, ForeignKey("areas.id"), nullable=True)
    ruta            = Column(Text, nullable=False)
    tamanio_bytes   = Column(BigInteger, nullable=True)
    contenido       = Column(Text, nullable=True)
    subido_por      = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_subida    = Column(DateTime, default=datetime.utcnow)
    fecha_documento = Column(Date, nullable=True)

    area_rel        = relationship("Area", back_populates="documentos")
    subido_por_rel  = relationship("Usuario", back_populates="documentos")
