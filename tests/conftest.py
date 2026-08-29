from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from busint_alertas.core.motor import ContextoEjecucion
from busint_alertas.motores.cartera import ConfiguracionCartera, Movimiento

CORTE = date(2026, 8, 31)
EMPRESA = "E01"


@pytest.fixture
def corte() -> date:
    return CORTE


def factura(
    dias_vencida: int,
    saldo: str = "1000000",
    nit: str = "900123456",
    numero: str = "F-001",
    empresa: str = EMPRESA,
    **extra,
) -> Movimiento:
    """Construye una factura que, al corte, lleva `dias_vencida` dias.

    Negativo significa por vencer. Es la forma mas legible de escribir los casos:
    se declara el resultado esperado del calculo, no las fechas crudas.
    """
    vencimiento = CORTE - timedelta(days=dias_vencida)
    return Movimiento(
        empresa_id=empresa,
        cliente_nit=nit,
        factura=numero,
        fecha_emision=vencimiento - timedelta(days=30),
        fecha_vencimiento=vencimiento,
        saldo=Decimal(saldo),
        **extra,
    )


@pytest.fixture
def config_completa() -> ConfiguracionCartera:
    """Configuracion con todos los parametros de fase 1 asignados."""
    return ConfiguracionCartera.plantilla(
        EMPRESA,
        dias_preventivos=5,
        n_facturas_vencidas=3,
        pct_mayor_90_umbral=Decimal("40"),
    )


@pytest.fixture
def contexto(config_completa) -> ContextoEjecucion:
    return ContextoEjecucion(
        empresa_id=EMPRESA, corte=CORTE, configuracion=config_completa
    )
