from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, documentos, usuarios, areas

app = FastAPI(
    title="Gestor Documental",
    description="Sistema de gestión documental multiusuario",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # en producción: lista de IPs clientes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,       prefix="/auth",       tags=["Auth"])
app.include_router(usuarios.router,   prefix="/usuarios",   tags=["Usuarios"])
app.include_router(areas.router,      prefix="/areas",      tags=["Áreas"])
app.include_router(documentos.router, prefix="/documentos", tags=["Documentos"])

@app.get("/")
def root():
    return {"status": "ok", "mensaje": "Gestor Documental API v1.0"}
