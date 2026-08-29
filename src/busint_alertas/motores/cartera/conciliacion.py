"""Cierre de alertas por ausencia (C-18).

§10.2 dice que al pagarse totalmente la factura la alerta pasa a cerrada. Pero
si el ERP solo expone cuentas abiertas, la factura pagada simplemente desaparece
del origen: no llega ningun evento de pago que el motor pueda escuchar.

La solucion es tratarlo como una conciliacion y no como un evento. En cada
corrida, toda alerta activa cuya factura ya no aparece entre las cuentas
abiertas se marca como cerrada por pago, registrando la fecha de deteccion.

La funcion es pura para poder probarla sin base de datos; en la fase 2 la
llamara el repositorio con las alertas activas del corte anterior.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Iterable, Sequence

from ...core.alerta import Alerta
from ...core.tipos import EstadoAlerta
from .datos import Movimiento


def cerrar_por_ausencia(
    alertas_activas: Sequence[Alerta],
    movimientos_del_corte: Iterable[Movimiento],
    corte: date,
) -> list[Alerta]:
    """Devuelve las alertas que deben marcarse como cerradas por pago.

    Solo se cierran alertas de ambito factura: una alerta de cliente (A10, A11)
    no desaparece porque una factura se pague, se recalcula en la corrida.
    """
    abiertas = {(m.cliente_nit, m.factura) for m in movimientos_del_corte}
    cerradas: list[Alerta] = []
    for alerta in alertas_activas:
        if alerta.estado is not EstadoAlerta.ACTIVA:
            continue
        if alerta.entidad is None:
            continue
        if (alerta.sujeto, alerta.entidad) in abiertas:
            continue
        cerradas.append(
            replace(
                alerta,
                estado=EstadoAlerta.CERRADA_POR_PAGO,
                datos={**alerta.datos, "fecha_deteccion_pago": corte},
            )
        )
    return cerradas
