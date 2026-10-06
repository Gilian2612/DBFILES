import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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

@app.get("/health")
def health():
    return {"status": "ok", "mensaje": "Gestor Documental API v1.0"}

# El frontend (index.html) lo sirve esta misma app en "/", así la página y la API
# comparten dirección y funcionan igual por WiFi o por Tailscale.
# Va al final para que las rutas de la API tengan prioridad.
FRONTEND_DIR = os.getenv("FRONTEND_DIR", os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
