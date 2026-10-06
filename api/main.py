import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from core.config import MAX_SUBIDA_MB, MAX_SUBIDA_BYTES
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

# Rechaza de entrada las subidas que declaran ser demasiado grandes, antes de recibir el archivo.
# El límite exacto por archivo se controla en routers/documentos.py.
@app.middleware("http")
async def limitar_tamanio_subida(request: Request, call_next):
    if request.method == "POST" and request.url.path.startswith("/documentos"):
        largo = request.headers.get("content-length")
        if largo and largo.isdigit() and int(largo) > MAX_SUBIDA_BYTES + 1024 * 1024:  # margen para los demás campos del formulario
            return JSONResponse(status_code=413, content={"detail": f"El archivo supera el límite de {MAX_SUBIDA_MB} MB"})
    return await call_next(request)

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
