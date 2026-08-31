"""Construye el origen de datos a partir del entorno.

Vive aparte de `arranque.py` a proposito. `arranque` construye la aplicacion
FastAPI al importarse, y eso exige la clave de firma de los tokens; la CLI
tomaba el origen de alli y acababa pidiendo una clave de sesion para correr un
corte, que no tiene nada que ver.

    BUSINT_ORIGEN     erp | excel | csv     (por defecto: erp)
    BUSINT_ERP_URL    URL base del API del ERP, si el origen es erp.
    BUSINT_ERP_TOKEN  token del ERP, si lo exige.
    BUSINT_ARCHIVO    ruta del .xlsx o .csv, si el origen es un archivo.
"""

from __future__ import annotations

import os

from .api import FuenteAPI
from .base import FuenteDatos
from .planos import MAPEO_BUSINT, FuenteCSV, FuenteExcel


def exigir(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(
            f"Falta la variable de entorno {nombre}. "
            f"Ver la cabecera de busint_alertas/fuentes/entorno.py."
        )
    return valor


def construir_fuente() -> FuenteDatos:
    """Elige el origen segun el entorno.

    El origen no llega en la peticion: quien consulta el panel no debe poder
    decidir de donde salen los datos.
    """
    clase = os.environ.get("BUSINT_ORIGEN", "erp").lower()

    if clase == "erp":
        return FuenteAPI(
            url_base=exigir("BUSINT_ERP_URL"),
            mapeo=MAPEO_BUSINT,
            token=os.environ.get("BUSINT_ERP_TOKEN"),
        )
    if clase == "excel":
        return FuenteExcel(exigir("BUSINT_ARCHIVO"))
    if clase == "csv":
        return FuenteCSV(exigir("BUSINT_ARCHIVO"))

    raise RuntimeError(
        f"BUSINT_ORIGEN='{clase}' no es valido. Usa: erp, excel o csv."
    )
