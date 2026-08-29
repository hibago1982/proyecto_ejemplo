"""Dependencias del API: sesion de base y empresa en contexto.

ADVERTENCIA SOBRE LA IDENTIDAD DE EMPRESA
-----------------------------------------
Hoy la empresa llega en una cabecera que el cliente controla. Eso NO es
autenticacion: cualquiera que alcance el API puede pedir la cartera de otra
empresa cambiando un valor.

Es un marcador de posicion consciente. §8.4 exige permisos y C-13 define los
cuatro roles, pero ambos son de la fase 8 del plan. Cuando esa fase llegue,
`empresa_en_contexto` debe resolverse desde el token de sesion del usuario y
no desde la peticion, y esta funcion es el unico punto que hay que cambiar.

La segunda linea de defensa ya esta puesta: la seguridad a nivel de fila de
PostgreSQL, que la migracion activa sobre las ocho tablas con `empresa_id`.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker

from ..core.fechas import hoy
from . import consultas

#: Se asigna al construir la aplicacion.
_fabrica: sessionmaker[Session] | None = None


def configurar_sesiones(fabrica: sessionmaker[Session]) -> None:
    global _fabrica
    _fabrica = fabrica


def obtener_sesion() -> Iterator[Session]:
    if _fabrica is None:
        raise RuntimeError(
            "El API no tiene fabrica de sesiones configurada. "
            "Usa crear_app(fabrica_de_sesiones(engine))."
        )
    with _fabrica() as sesion:
        try:
            yield sesion
            sesion.commit()
        except Exception:
            sesion.rollback()
            raise


SesionBD = Annotated[Session, Depends(obtener_sesion)]


def empresa_en_contexto(
    x_empresa_id: Annotated[
        str,
        Header(
            description="Empresa sobre la que se opera. PROVISIONAL: cuando "
            "exista autenticacion debe salir del token, no de la peticion.",
        ),
    ],
) -> str:
    if not x_empresa_id.strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "La cabecera X-Empresa-Id no puede ir vacia."
        )
    return x_empresa_id.strip()


Empresa = Annotated[str, Depends(empresa_en_contexto)]


def resolver_corte(
    sesion: SesionBD, empresa_id: Empresa, corte: date | None = None
) -> date:
    """Corte pedido, o el ultimo calculado si no se especifica.

    §7.4 hace de la fecha de corte un control de primer nivel: moverla recalcula
    todo el tablero. Por eso viaja como parametro en cada consulta y no como
    estado de sesion.
    """
    if corte is not None:
        return corte
    ultimo = consultas.ultimo_corte(sesion, empresa_id)
    if ultimo is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"La empresa '{empresa_id}' no tiene ningun corte calculado. "
            "Ejecuta el motor antes de consultar.",
        )
    return ultimo


CorteResuelto = Annotated[date, Depends(resolver_corte)]


def corte_de_hoy() -> date:
    """C-11: hoy segun America/Bogota, no segun el reloj del servidor."""
    return hoy()
