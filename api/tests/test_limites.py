"""
Pruebas para core/limites.py (LimiteRitmo).

Se crean instancias frescas en cada prueba para evitar interferencia
con los limitadores de módulo (limite_login, limite_subidas).
"""
import time
import threading

import pytest
from fastapi import HTTPException

from core.limites import LimiteRitmo


def test_bajo_el_limite_no_lanza():
    lr = LimiteRitmo(maximo=3, ventana=60, mensaje="límite")
    for _ in range(3):
        lr.registrar("clave")  # no debe lanzar


def test_superar_limite_lanza_429():
    lr = LimiteRitmo(maximo=3, ventana=60, mensaje="límite alcanzado")
    for _ in range(3):
        lr.registrar("clave")
    with pytest.raises(HTTPException) as exc:
        lr.registrar("clave")
    assert exc.value.status_code == 429
    assert "límite alcanzado" in exc.value.detail


def test_exactamente_en_el_limite():
    lr = LimiteRitmo(maximo=1, ventana=60, mensaje="límite")
    lr.registrar("clave")       # primera — debe pasar
    with pytest.raises(HTTPException):
        lr.registrar("clave")   # segunda — debe bloquearse


def test_claves_diferentes_son_independientes():
    lr = LimiteRitmo(maximo=2, ventana=60, mensaje="límite")
    lr.registrar("a")
    lr.registrar("a")
    lr.registrar("b")   # clave distinta — no debe verse afectada por "a"
    with pytest.raises(HTTPException):
        lr.registrar("a")   # "a" ya alcanzó su límite
    lr.registrar("b")   # "b" aún tiene margen


def test_ventana_expirada_permite_nuevas_peticiones():
    lr = LimiteRitmo(maximo=2, ventana=0.1, mensaje="límite")  # ventana de 100 ms
    lr.registrar("clave")
    lr.registrar("clave")
    time.sleep(0.15)            # esperar a que expire la ventana
    lr.registrar("clave")       # debe pasar de nuevo


def test_thread_safety():
    """Varios hilos registrando la misma clave: solo maximo peticiones deben pasar."""
    maximo = 5
    lr = LimiteRitmo(maximo=maximo, ventana=60, mensaje="límite")
    errores = []
    pasados = []

    def intentar():
        try:
            lr.registrar("compartida")
            pasados.append(1)
        except HTTPException:
            errores.append(1)

    hilos = [threading.Thread(target=intentar) for _ in range(maximo * 2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert len(pasados) == maximo
    assert len(errores) == maximo
