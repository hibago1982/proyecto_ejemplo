"""Dependencias del API: sesion de base y corte en contexto.

La identidad del usuario, su empresa y su rol viven en `seguridad.py` y salen
del token firmado. Hasta la etapa 7 llegaban en la cabecera `X-Empresa-Id`, que
el cliente controlaba: cualquiera podia leer y escribir en la cartera de otra
empresa cambiando un valor. Eso ya no es posible.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Iterator

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker

from ..core.fechas import hoy
from ..persistencia.usuarios import Identidad
from . import consultas
from .seguridad import Consulta

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


def empresa_de(quien: Consulta) -> str:
    """Empresa sobre la que opera quien hace la peticion.

    Sale del token. No hay forma de pedir otra empresa: el dato no viaja en la
    peticion, asi que no se puede cambiar sin invalidar la firma.
    """
    return quien.empresa_id


Empresa = Annotated[str, Depends(empresa_de)]


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
