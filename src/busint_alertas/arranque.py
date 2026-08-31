"""Arranque de la aplicacion para un despliegue real.

Lee la configuracion del entorno y no del codigo: la URL de la base, la clave de
firma y el origen de datos cambian entre desarrollo, piloto y produccion, y
ninguno de los tres deberia exigir tocar un archivo del repositorio.

    BUSINT_DB_URL=postgresql+psycopg://usuario:clave@host/busint_alertas \
    BUSINT_CLAVE_FIRMA=... \
    uvicorn busint_alertas.arranque:app

Variables que reconoce, ademas de las del origen de datos, que estan en
`fuentes/entorno.py`:

    BUSINT_DB_URL          obligatoria. La base del motor.
    BUSINT_CLAVE_FIRMA     obligatoria. Firma los tokens de sesion.
    BUSINT_EMPRESAS        empresas del recalculo diario, separadas por coma.
    BUSINT_HORA_CORTE      hora local de Bogota del recalculo (por defecto 5).
    BUSINT_PROGRAMAR       "1" para activar el recalculo diario.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

from .api import crear_app
from .fuentes.entorno import construir_fuente, exigir
from .persistencia import crear_engine, fabrica_de_sesiones

registro = logging.getLogger("busint.arranque")


def crear() -> FastAPI:
    engine = crear_engine(
        exigir("BUSINT_DB_URL"),
        # `pool_pre_ping` evita el fallo tipico tras una noche sin trafico: la
        # base cierra la conexion ociosa y la primera peticion de la manana la
        # encuentra muerta.
        pool_pre_ping=True,
        pool_size=int(os.environ.get("BUSINT_POOL", "5")),
    )
    exigir("BUSINT_CLAVE_FIRMA")  # falla al arrancar, no en la primera sesion

    fabrica = fabrica_de_sesiones(engine)
    fuente = construir_fuente()
    aplicacion = crear_app(fabrica, fuente=fuente)

    if os.environ.get("BUSINT_PROGRAMAR") == "1":
        from .planificador import Programacion, crear_planificador

        empresas = [
            e.strip() for e in os.environ.get("BUSINT_EMPRESAS", "").split(",") if e.strip()
        ]
        if not empresas:
            raise RuntimeError(
                "BUSINT_PROGRAMAR=1 exige BUSINT_EMPRESAS con al menos una empresa."
            )
        planificador = crear_planificador(
            Programacion(
                fabrica=fabrica, fuente=fuente, empresas=empresas,
                hora=int(os.environ.get("BUSINT_HORA_CORTE", "5")),
            )
        )
        # Se guarda en el estado para poder pararlo al apagar y para que las
        # pruebas puedan inspeccionarlo.
        aplicacion.state.planificador = planificador
        registro.info(
            "Recalculo diario programado a las %s:00 America/Bogota para %s",
            os.environ.get("BUSINT_HORA_CORTE", "5"), ", ".join(empresas),
        )

    return aplicacion


app = crear()
