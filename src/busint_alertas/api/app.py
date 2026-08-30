"""Aplicacion FastAPI del motor de alertas.

§4.2 lo fija: el motor de reglas no puede vivir en el navegador. Los umbrales
se custodian en el servidor, el calculo debe ser auditable, y pantalla, PDF y
Excel tienen que leer del mismo resultado persistido. Este API es ese punto
unico, y por eso el contrato OpenAPI que publica es tambien el documento del
que se generan los tipos del frontend.

La empresa y el rol de quien pide salen del token firmado, no de la peticion.
Hasta la etapa 7 llegaban en una cabecera que el cliente controlaba.
"""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from ..fuentes.base import FuenteDatos
from . import dependencias
from .rutas import configuracion, ejecucion, exportar, gestion, panel, sesion

DESCRIPCION = """
Motor de alertas de cartera de BUSINT.

Convierte el aging de cuentas por cobrar en una lista de trabajo priorizada.
Toda alerta lleva la explicacion de por que se disparo: la regla, el parametro
vigente y el valor que la disparo.

**Los montos viajan como cadena**, no como numero, para conservar los dos
decimales sin el error de redondeo de los flotantes de JavaScript.

Autenticacion: `POST /api/v1/sesion` devuelve un token; el resto de endpoints
lo esperan en `Authorization: Bearer`. Los permisos son acumulativos segun el
rol (Consulta, Gestor, Coordinador, Administrador).
"""


def crear_app(
    fabrica: sessionmaker[Session],
    fuente: FuenteDatos | None = None,
    titulo: str = "BUSINT - Motor de alertas de cartera",
) -> FastAPI:
    """Construye la aplicacion con sus dependencias ya resueltas.

    Recibe la fabrica de sesiones y el origen en vez de crearlos: es lo que
    permite montarla contra una base en memoria en las pruebas y contra
    PostgreSQL y el API del ERP en produccion, sin ramas dentro del codigo.
    """
    dependencias.configurar_sesiones(fabrica)
    if fuente is not None:
        ejecucion.configurar_fuente(fuente)

    app = FastAPI(
        title=titulo,
        version="0.1.0",
        description=DESCRIPCION,
        openapi_tags=[
            {"name": "panel", "description": "Panel de control (§8.1)"},
            {"name": "gestion", "description": "Lista de gestion y detalle de cliente (§8.2, §8.3)"},
            {"name": "configuracion", "description": "Reglas, umbrales y auditoria (§8.4, §10.3)"},
            {"name": "ejecucion", "description": "Corridas del motor (§10.2)"},
            {"name": "exportar", "description": "PDF y Excel del corte (§9)"},
            {"name": "sesion", "description": "Autenticacion y roles (§8.4, C-13)"},
        ],
    )

    for router in (
        sesion.router, panel.router, gestion.router,
        configuracion.router, ejecucion.router, exportar.router,
    ):
        app.include_router(router, prefix="/api/v1")

    @app.get("/salud", tags=["panel"], summary="Sonda de salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    return app
