from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from busint_alertas.api import crear_app  # noqa: E402
from busint_alertas.core.tipos import Rol  # noqa: E402
from busint_alertas.motores.cartera import Movimiento  # noqa: E402
from busint_alertas.persistencia import (  # noqa: E402
    crear_engine, crear_esquema, fabrica_de_sesiones, sembrar,
)
from busint_alertas.persistencia import usuarios as usuarios_bd  # noqa: E402
from busint_alertas.persistencia.usuarios import crear as crear_usuario  # noqa: E402

CLAVE = "clave-larga-de-prueba"

#: Un usuario por rol, para poder comprobar que cada endpoint exige el suyo.
USUARIOS = {
    Rol.CONSULTA: "ana",
    Rol.GESTOR: "gestor",
    Rol.COORDINADOR: "coord",
    Rol.ADMINISTRADOR: "admin",
}

EMPRESA = "E01"
CORTE = date(2026, 8, 21)

# La firma se fija en la prueba: sin BUSINT_CLAVE_FIRMA el API se niega a
# emitir tokens, que es justo lo que debe hacer en produccion.
os.environ.setdefault("BUSINT_CLAVE_FIRMA", "clave-de-prueba")


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


@pytest.fixture(autouse=True)
def cifrado_rapido(monkeypatch):
    """Baja el coste de PBKDF2 solo en estas pruebas.

    El coste real es deliberado, pero multiplicado por cinco usuarios y cada
    fixture convertia la suite en dos minutos. Se hace con monkeypatch y no
    asignando el modulo, para que no se filtre a `test_usuarios.py`, que si
    verifica el cifrado con el coste de produccion.
    """
    monkeypatch.setattr(usuarios_bd, "ITERACIONES", 1_000)


@pytest.fixture
def engine():
    """SQLite en memoria compartida entre conexiones.

    Sin StaticPool cada conexion abriria su propia base y el API no veria las
    tablas que creo la prueba.
    """
    return crear_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


@pytest.fixture
def fabrica(engine):
    crear_esquema(engine)
    F = fabrica_de_sesiones(engine)
    with F() as s:
        sembrar(
            s, EMPRESA, dias_preventivos=15, n_facturas_vencidas=3,
            pct_mayor_90_umbral=Decimal("40"),
        )
        for rol, nombre in USUARIOS.items():
            crear_usuario(s, nombre, CLAVE, EMPRESA, rol, nombre.title())
        # Un usuario de otra empresa, para comprobar el aislamiento.
        crear_usuario(s, "intruso", CLAVE, "E99", Rol.ADMINISTRADOR, "Intruso")
        s.commit()
    return F


@pytest.fixture
def cliente(fabrica):
    return TestClient(crear_app(fabrica, fuente=FuenteFalsa(CARTERA)))


def entrar(cliente, usuario: str = "admin") -> dict[str, str]:
    """Inicia sesion y devuelve la cabecera de autorizacion."""
    r = cliente.post(
        "/api/v1/sesion", json={"usuario": usuario, "clave": CLAVE}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def CABECERA(cliente):
    """Sesion de administrador: cubre todos los endpoints."""
    return entrar(cliente, "admin")


@pytest.fixture
def contar_consultas(engine):
    """Cuenta las sentencias SQL que coincidan con un texto.

    Sirve para fijar que una pantalla no degenere en N+1 consultas cuando
    alguien anada un campo mas adelante.
    """
    from sqlalchemy import event

    sentencias: list[str] = []

    def registrar(_conn, _cursor, sentencia, *_resto):
        sentencias.append(sentencia)

    event.listen(engine, "before_cursor_execute", registrar)
    yield lambda texto: sum(1 for s in sentencias if texto in s)
    event.remove(engine, "before_cursor_execute", registrar)


@pytest.fixture
def cliente_corrido(cliente, CABECERA):
    """API con un corte ya calculado."""
    respuesta = cliente.post(
        "/api/v1/ejecucion", json={"corte": str(CORTE)}, headers=CABECERA
    )
    assert respuesta.status_code == 200, respuesta.text
    return cliente
