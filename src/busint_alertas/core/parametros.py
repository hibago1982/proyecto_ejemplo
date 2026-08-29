"""Parametros administrables de las reglas.

Dos decisiones del analisis viven aqui:

C-05: cuando la empresa no ha asignado valor a un parametro, la regla queda
inactiva. El motor no asume ningun valor por defecto, porque un umbral inventado
por el programador produce alertas que nadie puede defender ante una junta.

C-06: los parametros se identifican por nombre propio y no por letras genericas.
`dias_preventivos` (R06) y `dias_sin_gestion` (A12) son independientes y se
configuran por separado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

#: Centinela para un parametro declarado pero sin valor asignado por la empresa.
SIN_DEFINIR = None


@dataclass(frozen=True)
class DefinicionParametro:
    """Declara que un parametro existe, sin decir cuanto vale."""

    nombre: str
    tipo: type
    descripcion: str


@dataclass(frozen=True)
class Parametros:
    """Valores vigentes de los parametros de una regla, para una empresa.

    Es el equivalente en memoria de la columna JSONB de `ar_alert_rule`. Se
    modela como mapa abierto y no como campos fijos justamente para que agregar
    una regla nueva no obligue a migrar el esquema.
    """

    valores: Mapping[str, Any] = field(default_factory=dict)

    def definido(self, nombre: str) -> bool:
        return self.valores.get(nombre, SIN_DEFINIR) is not SIN_DEFINIR

    def faltantes(self, requeridos: tuple[str, ...]) -> tuple[str, ...]:
        """Parametros requeridos que la empresa todavia no ha configurado."""
        return tuple(n for n in requeridos if not self.definido(n))

    def entero(self, nombre: str) -> int:
        return int(self._exigir(nombre))

    def decimal(self, nombre: str) -> Decimal:
        return Decimal(str(self._exigir(nombre)))

    def _exigir(self, nombre: str) -> Any:
        valor = self.valores.get(nombre, SIN_DEFINIR)
        if valor is SIN_DEFINIR:
            raise ParametroSinDefinir(nombre)
        return valor


class ParametroSinDefinir(LookupError):
    """Se leyo un parametro que la empresa no ha configurado.

    No deberia ocurrir en operacion normal: el motor consulta `faltantes` y
    desactiva la regla antes de evaluarla. Que se lance indica un error de
    programacion en una regla, no un dato faltante.
    """

    def __init__(self, nombre: str) -> None:
        super().__init__(
            f"El parametro '{nombre}' no tiene valor asignado por la empresa. "
            "La regla que lo usa debe permanecer inactiva (C-05)."
        )
        self.nombre = nombre
