"""Origenes de datos: archivo plano, API REST y, en la fase 2, lectura SQL directa.

Cambiar de origen no cambia el motor. Es lo que permite probar contra el archivo
de prueba y desplegar contra el ERP con la misma logica.

    from busint_alertas.fuentes import FuenteExcel, FuenteAPI

    fuente = FuenteExcel("cartera.xlsx")          # o
    fuente = FuenteAPI("https://erp.busint.co/api", MAPEO_BUSINT, token=...)

    movimientos = fuente.leer(empresa_id="E01", corte=date(2026, 8, 21))
"""

from .api import FuenteAPI, Transporte, TransporteHTTP
from .base import ErrorDeOrigen, FuenteDatos, MapeoCampos, construir_movimiento, normalizar
from .planos import MAPEO_BUSINT, FuenteCSV, FuenteExcel

__all__ = [
    "ErrorDeOrigen",
    "FuenteAPI",
    "FuenteCSV",
    "FuenteDatos",
    "FuenteExcel",
    "MAPEO_BUSINT",
    "MapeoCampos",
    "Transporte",
    "TransporteHTTP",
    "construir_movimiento",
    "normalizar",
]
