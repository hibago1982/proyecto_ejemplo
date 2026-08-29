"""Corrida completa: leer del origen, evaluar y persistir.

Es la pieza que llamara el planificador de §10.2, tanto en la ejecucion diaria
automatica como en el reproceso manual de un corte.

El orden importa y no es casual: el motor evalua sobre datos en memoria y solo
despues se escribe. Si algo falla a mitad, la transaccion se revierte entera y
el corte anterior queda intacto, en vez de dejar un corte a medio calcular que
nadie sabria distinguir de uno completo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy.orm import Session

from .core.motor import ContextoEjecucion, ResultadoMotor
from .core.tipos import Fase
from .fuentes.base import FuenteDatos
from .motores.cartera import MotorCartera
from .motores.cartera.configuracion import ConfiguracionCartera
from .persistencia import configuracion as config_bd
from .persistencia.gestion import construir_historial
from .persistencia.repositorio import RepositorioCartera, ResumenGuardado


@dataclass(frozen=True)
class Corrida:
    """Lo que produjo una ejecucion, para reportarlo al usuario o al log."""

    corte: date
    resultado: ResultadoMotor
    resumen: ResumenGuardado
    filas_leidas: int


def ejecutar_corte(
    sesion: Session,
    fuente: FuenteDatos,
    empresa_id: str,
    corte: date,
    fase_vigente: Fase = Fase.F5_GESTION,
    configuracion: ConfiguracionCartera | None = None,
) -> Corrida:
    """Corre el motor para un corte y persiste el resultado.

    `configuracion` se lee de la base salvo que se pase explicitamente, que es
    lo que permite simular un cambio de umbral sin guardarlo (§7.4, simulador).
    """
    config = configuracion or config_bd.cargar(sesion, empresa_id)
    repositorio = RepositorioCartera(sesion)
    bitacora = repositorio.abrir_ejecucion(empresa_id, corte)

    try:
        movimientos = list(fuente.leer(empresa_id, corte))
        contexto = ContextoEjecucion(
            empresa_id=empresa_id, corte=corte,
            configuracion=config, fase_vigente=fase_vigente,
            # A12 necesita saber desde cuando esta activa cada alerta y cuando
            # se gestiono por ultima vez. Se resuelve aqui y se pasa como dato,
            # porque el motor no consulta la base (§4.2).
            historial=construir_historial(sesion, empresa_id),
        )
        resultado = MotorCartera().evaluar(contexto, movimientos)
        resumen = repositorio.guardar(empresa_id, corte, resultado, config)
    except Exception as error:
        # La bitacora se escribe aparte para que el fallo quede registrado
        # aunque el resto de la transaccion se revierta.
        repositorio.cerrar_ejecucion(
            bitacora, _RESUMEN_VACIO, 0, estado="error", mensaje=str(error)[:500]
        )
        raise

    repositorio.cerrar_ejecucion(bitacora, resumen, len(movimientos))
    return Corrida(
        corte=corte, resultado=resultado, resumen=resumen,
        filas_leidas=len(movimientos),
    )


_RESUMEN_VACIO = ResumenGuardado(0, 0, 0, 0, "")
