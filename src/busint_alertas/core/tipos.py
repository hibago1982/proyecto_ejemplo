"""Vocabulario comun a todos los motores de alerta.

Estos tipos son deliberadamente independientes del dominio de cartera: un motor
de inventario o de tesoreria emite alertas con la misma forma, y por eso viven
aqui y no dentro de `motores/cartera`.
"""

from __future__ import annotations

from enum import Enum


class Prioridad(Enum):
    """Nivel de atencion que exige una alerta.

    El orden numerico permite ordenar la lista de trabajo y quedarse con la
    prioridad mas alta cuando varias reglas afectan a la misma entidad.
    """

    INFORMATIVA = 0
    MEDIA = 1
    ALTA = 2
    MUY_ALTA = 3
    CRITICA = 4

    @property
    def etiqueta(self) -> str:
        return {
            Prioridad.INFORMATIVA: "Informativa",
            Prioridad.MEDIA: "Media",
            Prioridad.ALTA: "Alta",
            Prioridad.MUY_ALTA: "Muy alta",
            Prioridad.CRITICA: "Critica",
        }[self]

    def __lt__(self, otra: "Prioridad") -> bool:
        return self.value < otra.value

    def elevar(self, niveles: int = 1) -> "Prioridad":
        """Sube la prioridad sin pasarse de Critica.

        R01 "eleva la prioridad al menos un nivel": no emite alerta propia,
        agrava la que ya tiene la factura por su antiguedad.
        """
        return Prioridad(min(self.value + niveles, Prioridad.CRITICA.value))


class EstadoAlerta(Enum):
    """Ciclo de vida de una alerta.

    CERRADA_POR_PAGO se determina por ausencia en el origen, no por un evento
    del ERP (C-18): el motor la marca cuando la entidad deja de aparecer.
    """

    ACTIVA = "activa"
    CERRADA_POR_PAGO = "cerrada_por_pago"
    CERRADA_MANUAL = "cerrada_manual"


class Fase(Enum):
    """Fase del plan de desarrollo en la que una regla queda operativa.

    Una regla declarada en una fase posterior a la vigente no se evalua. Es lo
    que evita el problema de C-07: A12 depende del historial de gestion, que no
    existe hasta la fase 5, y evaluarla antes la dispararia siempre.
    """

    F1_MOTOR = 1
    F2_PERSISTENCIA = 2
    F3_API = 3
    F4_PANEL = 4
    F5_GESTION = 5
