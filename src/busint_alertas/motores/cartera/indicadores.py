"""Indicadores agregados de §6.

C-14 se materializa aqui como una invariante comprobada, no como un comentario:
`cartera_total == por_vencer + vence_hoy + vencida`. La especificacion definia
cartera vencida como dias > 0, lo que dejaba el bucket "vence hoy" fuera de
ambos lados y hacia que los indicadores no sumaran el total.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ...core.dinero import monto, porcentaje
from ...core.tipos import Prioridad
from .buckets import Bucket

CERO = Decimal("0.00")


@dataclass
class PerfilCliente:
    """Estado agregado de un cliente en un corte. Equivale a `ar_riesgo_cliente`."""

    cliente_nit: str
    cliente_nombre: str = ""
    por_vencer: Decimal = CERO
    vence_hoy: Decimal = CERO
    vencida: Decimal = CERO
    mayor_90: Decimal = CERO
    mayor_150: Decimal = CERO
    dias_max: int = 0
    n_facturas: int = 0
    n_vencidas: int = 0
    prioridad: Prioridad = Prioridad.INFORMATIVA
    marcadores: list[str] = field(default_factory=list)
    por_bucket: dict[str, Decimal] = field(default_factory=dict)
    """Totales por bucket. Es lo que congela el snapshot del corte (C-16)."""

    @property
    def cartera_total(self) -> Decimal:
        """C-14: la identidad explicita. Total = por vencer + vence hoy + vencida."""
        return monto(self.por_vencer + self.vence_hoy + self.vencida)

    @property
    def pct_vencida(self) -> Decimal:
        return porcentaje(self.vencida, self.cartera_total)

    @property
    def pct_90(self) -> Decimal:
        return porcentaje(self.mayor_90, self.cartera_total)

    def acumular(self, saldo: Decimal, dias: int, bucket: Bucket) -> None:
        """Suma una factura al perfil, clasificandola segun su bucket."""
        self.n_facturas += 1
        self.por_bucket[bucket.codigo] = monto(
            self.por_bucket.get(bucket.codigo, CERO) + saldo
        )
        if bucket.es_por_vencer:
            self.por_vencer = monto(self.por_vencer + saldo)
        elif bucket.es_vence_hoy:
            self.vence_hoy = monto(self.vence_hoy + saldo)
        else:
            self.vencida = monto(self.vencida + saldo)
            self.n_vencidas += 1

        # Los cortes de 90 y 150 son indicadores de §6 y no dependen de como la
        # empresa haya configurado sus buckets: se calculan sobre los dias.
        if dias > 90:
            self.mayor_90 = monto(self.mayor_90 + saldo)
        if dias > 150:
            self.mayor_150 = monto(self.mayor_150 + saldo)

        self.dias_max = max(self.dias_max, dias)


@dataclass
class IndicadoresGlobales:
    """Cifras del panel de control para el corte completo."""

    por_vencer: Decimal = CERO
    vence_hoy: Decimal = CERO
    vencida: Decimal = CERO
    mayor_90: Decimal = CERO
    mayor_150: Decimal = CERO
    n_clientes: int = 0
    n_facturas: int = 0
    por_bucket: dict[str, Decimal] = field(default_factory=dict)
    facturas_por_bucket: dict[str, int] = field(default_factory=dict)

    @property
    def cartera_total(self) -> Decimal:
        return monto(self.por_vencer + self.vence_hoy + self.vencida)

    @property
    def pct_vencida(self) -> Decimal:
        return porcentaje(self.vencida, self.cartera_total)

    @property
    def pct_90(self) -> Decimal:
        return porcentaje(self.mayor_90, self.cartera_total)

    def acumular(self, saldo: Decimal, dias: int, bucket: Bucket) -> None:
        self.n_facturas += 1
        if bucket.es_por_vencer:
            self.por_vencer = monto(self.por_vencer + saldo)
        elif bucket.es_vence_hoy:
            self.vence_hoy = monto(self.vence_hoy + saldo)
        else:
            self.vencida = monto(self.vencida + saldo)
        if dias > 90:
            self.mayor_90 = monto(self.mayor_90 + saldo)
        if dias > 150:
            self.mayor_150 = monto(self.mayor_150 + saldo)
        self.por_bucket[bucket.codigo] = monto(
            self.por_bucket.get(bucket.codigo, CERO) + saldo
        )
        self.facturas_por_bucket[bucket.codigo] = (
            self.facturas_por_bucket.get(bucket.codigo, 0) + 1
        )

    def como_dict(self) -> dict:
        return {
            "cartera_total": self.cartera_total,
            "por_vencer": self.por_vencer,
            "vence_hoy": self.vence_hoy,
            "vencida": self.vencida,
            "pct_vencida": self.pct_vencida,
            "mayor_90": self.mayor_90,
            "pct_90": self.pct_90,
            "mayor_150": self.mayor_150,
            "n_clientes": self.n_clientes,
            "n_facturas": self.n_facturas,
            "por_bucket": dict(self.por_bucket),
            "facturas_por_bucket": dict(self.facturas_por_bucket),
        }
