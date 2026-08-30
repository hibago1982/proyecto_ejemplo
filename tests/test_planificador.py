"""Ejecucion programada (§10.2)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy.pool import StaticPool  # noqa: E402

from busint_alertas.persistencia import (  # noqa: E402
    crear_engine, crear_esquema, fabrica_de_sesiones, sembrar,
)
from busint_alertas.planificador import Programacion, correr_una_vez  # noqa: E402

from tests.persistencia.test_reproceso import CARTERA, CORTE, FuenteFalsa  # noqa: E402


@pytest.fixture
def fabrica():
    engine = crear_engine(
        "sqlite+pysqlite:///:memory:", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    crear_esquema(engine)
    F = fabrica_de_sesiones(engine)
    for empresa in ("E01", "E02"):
        with F() as s:
            sembrar(s, empresa, dias_preventivos=15, n_facturas_vencidas=3,
                    pct_mayor_90_umbral=Decimal("40"))
            s.commit()
    return F


def test_recalcula_todas_las_empresas(fabrica):
    programacion = Programacion(
        fabrica=fabrica, fuente=FuenteFalsa(CARTERA), empresas=("E01", "E02")
    )
    desenlaces = correr_una_vez(programacion, CORTE)
    assert set(desenlaces) == {"E01", "E02"}
    assert all(d.startswith("ok:") for d in desenlaces.values())


def test_un_fallo_no_detiene_a_las_demas(fabrica):
    """Si el ERP de una empresa no responde, las otras deben quedar al dia."""
    from busint_alertas.fuentes.base import ErrorDeOrigen

    class FuenteCaprichosa:
        def leer(self, empresa_id, corte):
            if empresa_id == "E01":
                raise ErrorDeOrigen("el ERP no responde")
            return iter(CARTERA)

    desenlaces = correr_una_vez(
        Programacion(fabrica=fabrica, fuente=FuenteCaprichosa(), empresas=("E01", "E02")),
        CORTE,
    )
    assert desenlaces["E01"].startswith("error:")
    assert desenlaces["E02"].startswith("ok:")


def test_el_fallo_queda_en_la_bitacora(fabrica):
    """§10.2: la bitacora es donde se mira que paso de madrugada."""
    from sqlalchemy import select

    from busint_alertas.persistencia.modelo import Ejecucion

    class FuenteCaida:
        def leer(self, empresa_id, corte):
            raise RuntimeError("sin conexion")

    correr_una_vez(
        Programacion(fabrica=fabrica, fuente=FuenteCaida(), empresas=("E01",)), CORTE
    )
    with fabrica() as s:
        fila = s.scalars(select(Ejecucion)).one()
        assert fila.estado == "error"
        assert "sin conexion" in fila.mensaje


def test_reprocesar_el_mismo_corte_no_duplica(fabrica):
    """La corrida programada usa la misma funcion que el boton manual."""
    programacion = Programacion(
        fabrica=fabrica, fuente=FuenteFalsa(CARTERA), empresas=("E01",)
    )
    correr_una_vez(programacion, CORTE)
    segunda = correr_una_vez(programacion, CORTE)
    assert "0 alertas nuevas" in segunda["E01"]


def test_se_programa_a_las_cinco_en_bogota(fabrica):
    """C-11: la hora es de America/Bogota, no del reloj del servidor."""
    apscheduler = pytest.importorskip("apscheduler")  # noqa: F841

    from busint_alertas.planificador import crear_planificador

    planificador = crear_planificador(
        Programacion(fabrica=fabrica, fuente=FuenteFalsa(CARTERA), empresas=("E01",)),
        iniciar=False,
    )
    tarea = planificador.get_job("recalculo_diario")
    assert str(tarea.trigger.timezone) == "America/Bogota"
    assert tarea.coalesce is True
