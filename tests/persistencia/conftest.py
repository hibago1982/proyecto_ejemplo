from __future__ import annotations

from decimal import Decimal

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")

from busint_alertas.persistencia import (  # noqa: E402
    crear_engine, crear_esquema, fabrica_de_sesiones, sembrar,
)

EMPRESA = "E01"


@pytest.fixture
def sesion():
    """Base en memoria. El destino es PostgreSQL 16; el modelo es portable."""
    engine = crear_engine("sqlite+pysqlite:///:memory:")
    crear_esquema(engine)
    Sesion = fabrica_de_sesiones(engine)
    with Sesion() as s:
        yield s


@pytest.fixture
def sesion_sembrada(sesion):
    sembrar(
        sesion, EMPRESA,
        dias_preventivos=15,
        n_facturas_vencidas=3,
        pct_mayor_90_umbral=Decimal("40"),
    )
    return sesion
