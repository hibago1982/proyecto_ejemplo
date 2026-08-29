#!/usr/bin/env python3
"""Levanta el API con el archivo de prueba cargado, para ver el panel funcionando.

Es una demostracion, no un arranque de produccion: usa SQLite en memoria y el
archivo de prueba sintetico. El arranque real apunta a PostgreSQL y a la
FuenteAPI del ERP, cambiando solo esas dos lineas.
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from sqlalchemy.pool import StaticPool  # noqa: E402

from busint_alertas.api import crear_app  # noqa: E402
from busint_alertas.ejecucion import ejecutar_corte  # noqa: E402
from busint_alertas.fuentes import FuenteExcel  # noqa: E402
from busint_alertas.persistencia import (  # noqa: E402
    crear_engine, crear_esquema, fabrica_de_sesiones, sembrar,
)

ARCHIVO = RAIZ / "tests" / "datos" / "cartera_busint_sintetica.xlsx"
CORTE = date(2026, 8, 21)
EMPRESA = "E01"


def construir():
    engine = crear_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    crear_esquema(engine)
    fabrica = fabrica_de_sesiones(engine)
    fuente = FuenteExcel(ARCHIVO)

    with fabrica() as sesion:
        sembrar(
            sesion, EMPRESA, dias_preventivos=15, n_facturas_vencidas=3,
            pct_mayor_90_umbral=Decimal("40"),
        )
        sesion.commit()
        corrida = ejecutar_corte(sesion, fuente, EMPRESA, CORTE)
        sesion.commit()
        print(
            f"Corte {CORTE}: {corrida.filas_leidas} facturas, "
            f"{corrida.resumen.alertas_insertadas} alertas, "
            f"{corrida.resumen.clientes} clientes."
        )

    return crear_app(fabrica, fuente=fuente)


app = construir()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
