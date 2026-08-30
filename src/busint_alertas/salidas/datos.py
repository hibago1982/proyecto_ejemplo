"""Los datos que alimentan pantalla, PDF y Excel.

§16 lo exige sin ambiguedad: "No duplicar la logica de alerta en PDF, Excel y
pantalla; debe existir una sola fuente de calculo". Y §13 lo convierte en
criterio de aceptacion: "El PDF y Excel muestran exactamente la misma
clasificacion que la pantalla para el mismo corte".

La unica forma de garantizarlo es que las tres salidas lean de aqui. Este modulo
no calcula nada: lee lo que el motor ya persistio. Si alguna vez alguien
necesita "ajustar" una cifra para el PDF, el sitio correcto es el motor, no una
excepcion en el generador.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Sequence

from sqlalchemy.orm import Session

from ..api import consultas
from ..core.dinero import monto
from ..core.tipos import Prioridad
from ..persistencia import modelo

CERO = Decimal("0.00")


@dataclass(frozen=True)
class Corte:
    """Todo lo que necesita una salida formal para un corte."""

    empresa_id: str
    corte: date
    generado: datetime
    version_parametros: str
    alertas: Sequence[modelo.Alerta]
    clientes: Sequence[modelo.RiesgoCliente]
    buckets: Sequence[modelo.AgingParam]
    totales_por_bucket: dict[str, Decimal]
    facturas_por_bucket: dict[str, int]
    nombres: dict[str, str] = field(default_factory=dict)

    @property
    def cartera_total(self) -> Decimal:
        return monto(sum((c.cartera_total for c in self.clientes), CERO))

    @property
    def por_vencer(self) -> Decimal:
        return monto(sum((c.por_vencer for c in self.clientes), CERO))

    @property
    def vence_hoy(self) -> Decimal:
        return monto(sum((c.vence_hoy for c in self.clientes), CERO))

    @property
    def vencida(self) -> Decimal:
        return monto(sum((c.vencida for c in self.clientes), CERO))

    @property
    def mayor_90(self) -> Decimal:
        return monto(sum((c.mayor_90 for c in self.clientes), CERO))

    @property
    def mayor_150(self) -> Decimal:
        return monto(sum((c.mayor_150 for c in self.clientes), CERO))

    def nombre_de(self, nit: str) -> str:
        return self.nombres.get(nit, "")

    @staticmethod
    def etiqueta_prioridad(valor: int) -> str:
        return Prioridad(valor).etiqueta


def cargar(sesion: Session, empresa_id: str, corte: date) -> Corte:
    """Reune el corte completo desde lo persistido, sin recalcular nada."""
    cabeceras = [c for c in consultas.cortes(sesion, empresa_id) if c["corte"] == corte]
    if not cabeceras:
        raise LookupError(
            f"La empresa '{empresa_id}' no tiene calculado el corte {corte}."
        )
    cabecera = cabeceras[0]
    clientes = consultas.riesgo(sesion, empresa_id, corte)

    return Corte(
        empresa_id=empresa_id,
        corte=corte,
        generado=cabecera["generado"],
        version_parametros=cabecera["version_parametros"],
        alertas=consultas.lista_gestion(
            sesion, empresa_id, corte, estado=None, por_pagina=1_000_000
        )[1],
        clientes=clientes,
        buckets=consultas.buckets_configurados(sesion, empresa_id),
        totales_por_bucket=consultas.totales_por_bucket(sesion, empresa_id, corte),
        facturas_por_bucket=consultas.facturas_por_bucket(sesion, empresa_id, corte),
        nombres={c.cliente_nit: c.cliente_nombre for c in clientes},
    )
