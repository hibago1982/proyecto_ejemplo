"""Ejecucion programada del motor (§10.2).

"Permitir ejecucion automatica diaria" y "registrar fecha y hora de la ultima
evaluacion". Se apoya en APScheduler, que es lo que §5 propone para arrancar:
basta mientras el recalculo no pase del minuto ni haya muchas empresas
concurrentes; cuando eso cambie, se migra a Celery sin tocar esta interfaz.

La corrida programada llama exactamente a la misma funcion que el boton de
reproceso manual. Que no existan dos caminos es lo que evita que diverjan y que
el corte nocturno de un resultado distinto al que se ve en pantalla.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Callable, Sequence

from sqlalchemy.orm import Session, sessionmaker

from .core.fechas import ZONA_MOTOR, hoy
from .ejecucion import ejecutar_corte
from .fuentes.base import FuenteDatos

registro = logging.getLogger("busint.planificador")


@dataclass
class Programacion:
    """Que empresas se recalculan, con que origen y a que hora."""

    fabrica: sessionmaker[Session]
    fuente: FuenteDatos
    empresas: Sequence[str]
    hora: int = 5
    minuto: int = 0
    """Por defecto a las 05:00 de America/Bogota (C-11), antes de la jornada."""


def correr_una_vez(
    programacion: Programacion, corte: date | None = None
) -> dict[str, str]:
    """Recalcula todas las empresas. Devuelve el desenlace de cada una.

    Un fallo en una empresa no detiene a las demas: si el ERP de una no
    responde, las otras deben quedar igualmente actualizadas por la manana. El
    fallo queda en `ar_ejecucion`, que es donde se mira.
    """
    fecha = corte or hoy()
    desenlaces: dict[str, str] = {}

    for empresa_id in programacion.empresas:
        try:
            with programacion.fabrica() as sesion:
                corrida = ejecutar_corte(
                    sesion, programacion.fuente, empresa_id, fecha
                )
                sesion.commit()
            desenlaces[empresa_id] = (
                f"ok: {corrida.filas_leidas} filas, "
                f"{corrida.resumen.alertas_insertadas} alertas nuevas, "
                f"{corrida.resumen.alertas_cerradas} cerradas"
            )
            registro.info("Corte %s de %s: %s", fecha, empresa_id, desenlaces[empresa_id])
        except Exception as error:  # noqa: BLE001
            desenlaces[empresa_id] = f"error: {error}"
            registro.exception("Fallo el corte %s de %s", fecha, empresa_id)

    return desenlaces


def crear_planificador(programacion: Programacion, iniciar: bool = True):
    """Programa el recalculo diario.

    `coalesce` y `misfire_grace_time` importan: si el servicio estuvo caido a la
    hora prevista, interesa una sola corrida al volver y no una por cada
    disparo perdido.
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    planificador = BackgroundScheduler(timezone=ZONA_MOTOR)
    planificador.add_job(
        lambda: correr_una_vez(programacion),
        CronTrigger(
            hour=programacion.hora, minute=programacion.minuto, timezone=ZONA_MOTOR
        ),
        id="recalculo_diario",
        name="Recalculo diario de cartera",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    if iniciar:
        planificador.start()
    return planificador
