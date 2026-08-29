from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from busint_alertas.api import crear_app  # noqa: E402
from busint_alertas.motores.cartera import Movimiento  # noqa: E402
from busint_alertas.persistencia import (  # noqa: E402
    crear_engine, crear_esquema, fabrica_de_sesiones, sembrar,
)

EMPRESA = "E01"
CORTE = date(2026, 8, 21)
CABECERA = {"X-Empresa-Id": EMPRESA}


def factura(numero, dias, saldo="1000000", nit="900", vendedor="ANA", zona="NORTE"):
    venc = CORTE - timedelta(days=dias)
    return Movimiento(
        empresa_id=EMPRESA, cliente_nit=nit, factura=numero,
        fecha_emision=venc - timedelta(days=30), fecha_vencimiento=venc,
        saldo=Decimal(saldo), cliente_nombre="Cliente Demo",
        vendedor=vendedor, zona=zona,
    )


CARTERA = [
    factura("F-1", -10), factura("F-2", 0), factura("F-3", 15),
    factura("F-4", 45, vendedor="LUIS", zona="SUR"),
    factura("F-5", 100), factura("F-6", 200),
]


class FuenteFalsa:
    def __init__(self, movimientos):
        self.movimientos = list(movimientos)

    def leer(self, empresa_id, corte):
        return iter(self.movimientos)


@pytest.fixture
def fabrica():
    """SQLite en memoria compartida entre conexiones.

    Sin StaticPool cada conexion abriria su propia base y el API no veria las
    tablas que creo la prueba.
    """
    engine = crear_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    crear_esquema(engine)
    F = fabrica_de_sesiones(engine)
    with F() as s:
        sembrar(
            s, EMPRESA, dias_preventivos=15, n_facturas_vencidas=3,
            pct_mayor_90_umbral=Decimal("40"),
        )
        s.commit()
    return F


@pytest.fixture
def cliente(fabrica):
    return TestClient(crear_app(fabrica, fuente=FuenteFalsa(CARTERA)))


@pytest.fixture
def cliente_corrido(cliente):
    """API con un corte ya calculado."""
    respuesta = cliente.post(
        "/api/v1/ejecucion", json={"corte": str(CORTE)}, headers=CABECERA
    )
    assert respuesta.status_code == 200, respuesta.text
    return cliente
