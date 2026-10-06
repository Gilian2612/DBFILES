import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException


class LimiteRitmo:
    """Permite como máximo `maximo` acciones por clave en los últimos `ventana` segundos.

    Se guarda en memoria: se reinicia con el servidor y solo vale con un único proceso de uvicorn.
    """

    def __init__(self, maximo: int, ventana: int, mensaje: str):
        self.maximo = maximo
        self.ventana = ventana
        self.mensaje = mensaje
        self._recientes: dict = defaultdict(deque)
        self._candado = threading.Lock()  # los endpoints "def" corren en varios hilos a la vez

    def registrar(self, clave):
        """Cuenta una acción para `clave`, o responde 429 si ya se alcanzó el límite."""
        ahora = time.monotonic()
        with self._candado:
            recientes = self._recientes[clave]
            while recientes and ahora - recientes[0] >= self.ventana:
                recientes.popleft()
            if len(recientes) >= self.maximo:
                raise HTTPException(status_code=429, detail=self.mensaje)
            recientes.append(ahora)
