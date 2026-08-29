"""Historial de gestion visto por el motor.

A12 se dispara cuando una alerta lleva X dias activa sin gestion registrada.
Eso obliga al motor a conocer algo que no esta en las cuentas por cobrar: desde
cuando existe cada alerta y cuando se gestiono por ultima vez.

La regla de oro de §4.2 sigue en pie: el motor no consulta la base. Recibe ese
historial ya resuelto como parte del contexto, igual que recibe los movimientos.
Asi la evaluacion sigue siendo pura y reproducible, y las pruebas de A12 no
necesitan base de datos.

C-07 explica por que esto no podia existir antes: sin historial de gestion, A12
se disparaba siempre, porque ninguna alerta tenia gestion contra la cual
evaluarse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Mapping

#: Clave de una alerta de factura: cliente y numero de factura.
Clave = tuple[str, str]


@dataclass(frozen=True)
class HistorialGestion:
    """Que se sabe de la gestion de cada factura, al momento del corte."""

    ultima_gestion: Mapping[Clave, date] = field(default_factory=dict)
    """Fecha de la ultima gestion registrada, por factura."""

    alerta_desde: Mapping[Clave, date] = field(default_factory=dict)
    """Primer corte en que aparecio la alerta de esa factura.

    Es la referencia cuando nunca se ha gestionado: una alerta recien nacida no
    puede estar "sin gestion desde hace X dias".
    """

    def dias_sin_gestion(self, clave: Clave, corte: date) -> int | None:
        """Dias transcurridos sin gestion, o None si no aplica.

        Devuelve None cuando la alerta es nueva en este corte: no hay desde
        cuando contar, y contar desde hoy daria cero para todas.
        """
        referencia = self.ultima_gestion.get(clave) or self.alerta_desde.get(clave)
        if referencia is None:
            return None
        return (corte - referencia).days

    def fue_gestionada(self, clave: Clave) -> bool:
        return clave in self.ultima_gestion


#: Historial vacio, para cuando el motor corre sin persistencia (etapa 1).
SIN_HISTORIAL = HistorialGestion()
