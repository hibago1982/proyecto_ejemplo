"""Arranque y CLI.

Nacen de dos defectos que solo aparecieron al seguir la guia de despliegue en
una maquina limpia, no al escribir el codigo.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


def test_construir_fuente_no_exige_la_clave_de_firma(monkeypatch, tmp_path):
    """La CLI tomaba el origen de `arranque`, que construye el API al
    importarse. Correr un corte acababa pidiendo la clave de sesion del API."""
    monkeypatch.delenv("BUSINT_CLAVE_FIRMA", raising=False)
    monkeypatch.setenv("BUSINT_ORIGEN", "excel")
    monkeypatch.setenv("BUSINT_ARCHIVO", str(tmp_path / "cartera.xlsx"))

    from busint_alertas.fuentes.entorno import construir_fuente

    assert construir_fuente() is not None


def test_un_origen_desconocido_dice_cuales_valen(monkeypatch):
    monkeypatch.setenv("BUSINT_ORIGEN", "telepatia")
    from busint_alertas.fuentes.entorno import construir_fuente

    with pytest.raises(RuntimeError, match="erp, excel o csv"):
        construir_fuente()


def test_falta_la_ruta_del_archivo(monkeypatch):
    monkeypatch.setenv("BUSINT_ORIGEN", "excel")
    monkeypatch.delenv("BUSINT_ARCHIVO", raising=False)
    from busint_alertas.fuentes.entorno import construir_fuente

    with pytest.raises(RuntimeError, match="BUSINT_ARCHIVO"):
        construir_fuente()


def test_la_cli_sin_base_lo_dice_sin_traceback(monkeypatch):
    """Un traceback ante una variable que falta hace pensar que se rompio."""
    entorno = {"PATH": "/usr/bin:/bin", "PYTHONPATH": "src"}
    salida = subprocess.run(
        [sys.executable, "-m", "busint_alertas.cli", "estado", "E01"],
        capture_output=True, text=True, env=entorno, timeout=60,
    )
    assert salida.returncode != 0
    assert "Traceback" not in salida.stderr
    assert "BUSINT_DB_URL" in salida.stderr
