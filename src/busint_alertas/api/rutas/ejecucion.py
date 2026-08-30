"""Ejecucion del motor (§10.2): corrida manual y bitacora.

§10.2 pide ejecucion manual para reprocesar un corte y ejecucion automatica
diaria. Aqui va la manual; la programada la disparara APScheduler llamando a la
misma funcion, para que no existan dos caminos que puedan divergir.

La fuente de datos se inyecta al construir la aplicacion y no llega en la
peticion: quien consulta el panel no debe poder elegir de donde salen los datos.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ...ejecucion import ejecutar_corte
from ...fuentes.base import ErrorDeOrigen, FuenteDatos
from .. import consultas
from ..dependencias import Empresa, SesionBD, corte_de_hoy
from ..seguridad import Coordinador
from ..esquemas import Ejecucion, PeticionEjecucion, ResultadoEjecucion

router = APIRouter(tags=["ejecucion"])

#: Origen configurado al construir la aplicacion.
_fuente: FuenteDatos | None = None


def configurar_fuente(fuente: FuenteDatos) -> None:
    global _fuente
    _fuente = fuente


@router.post(
    "/ejecucion",
    response_model=ResultadoEjecucion,
    status_code=status.HTTP_200_OK,
    summary="Ejecutar el motor para un corte",
)
def ejecutar(
    sesion: SesionBD, quien: Coordinador, peticion: PeticionEjecucion
) -> ResultadoEjecucion:
    """§10.2: reproceso manual. C-13 lo reserva al coordinador."""
    empresa_id = quien.empresa_id
    if _fuente is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El API no tiene origen de datos configurado.",
        )
    corte = peticion.corte or corte_de_hoy()
    try:
        corrida = ejecutar_corte(sesion, _fuente, empresa_id, corte)
    except ErrorDeOrigen as e:
        # El origen fallo, no el motor. Se distingue para que quien opera sepa
        # si revisar el ERP o el codigo.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from None
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from None

    return ResultadoEjecucion(
        empresa_id=empresa_id, corte=corrida.corte,
        filas_leidas=corrida.filas_leidas,
        alertas_insertadas=corrida.resumen.alertas_insertadas,
        alertas_actualizadas=corrida.resumen.alertas_actualizadas,
        alertas_cerradas=corrida.resumen.alertas_cerradas,
        clientes=corrida.resumen.clientes,
        version_parametros=corrida.resumen.version_parametros,
        reglas_inactivas=dict(corrida.resultado.reglas_inactivas),
    )


@router.get(
    "/ejecucion", response_model=list[Ejecucion], summary="Bitacora de corridas"
)
def bitacora(
    sesion: SesionBD, empresa_id: Empresa, limite: int = 20
) -> list[Ejecucion]:
    return [
        Ejecucion.model_validate(f)
        for f in consultas.ejecuciones(sesion, empresa_id, limite)
    ]
