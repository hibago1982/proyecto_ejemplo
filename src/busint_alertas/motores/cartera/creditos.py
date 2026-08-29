"""Aplicacion de notas credito y abonos (C-10).

Decision de negocio: el ERP entrega el credito sin netear, en la columna
`Valor Credito`. El credito pertenece al cliente, no a la factura en cuya fila
viaja, y se aplica a la factura mas antigua. El saldo neto resultante es el que
usan las reglas y el que muestra la alerta.

Tres consecuencias de esa regla que el codigo resuelve de forma explicita:

  * Si el credito supera la factura mas antigua, el remanente pasa a la
    siguiente, y asi sucesivamente. La regla dice "la mas antigua" pero un
    credito mayor tiene que ir a algun lado, y descartarlo perderia dinero.
  * Si sobra credito despues de cubrir todas las facturas, el sobrante queda
    registrado como credito a favor del cliente. Nunca se produce un saldo
    negativo, que apareceria en el aging como una cifra sin sentido.
  * Una factura que el credito deja en cero queda saldada y no genera alerta.

Toda la operacion queda registrada en un `AplicacionCredito` por cliente: de
cuanto credito se partio, a que facturas fue y cuanto quedo sin aplicar. Sin ese
registro, un saldo que no coincide con el ERP seria imposible de explicar.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Iterable, Sequence

from ...core.dinero import monto
from .datos import Movimiento

CERO = Decimal("0.00")


@dataclass(frozen=True)
class AplicacionCredito:
    """Rastro auditable de como se repartio el credito de un cliente."""

    cliente_nit: str
    credito_total: Decimal
    aplicaciones: tuple[tuple[str, Decimal], ...]
    """Pares (numero de factura, monto aplicado), en el orden en que se aplico."""

    no_aplicado: Decimal
    """Credito a favor del cliente que ninguna factura abierta absorbio."""

    @property
    def facturas_saldadas(self) -> tuple[str, ...]:
        return tuple(f for f, _ in self.aplicaciones)

    def __str__(self) -> str:
        detalle = ", ".join(f"{f}: {m}" for f, m in self.aplicaciones) or "ninguna"
        return (
            f"Cliente {self.cliente_nit}: credito {self.credito_total} "
            f"aplicado a [{detalle}]; sin aplicar {self.no_aplicado}"
        )


def aplicar_creditos(
    movimientos: Iterable[Movimiento],
) -> tuple[list[Movimiento], list[AplicacionCredito]]:
    """Netea los creditos de cada cliente contra sus facturas mas antiguas.

    Devuelve los movimientos con el saldo neto y el rastro de la aplicacion.
    Es una funcion pura: no depende del orden en que lleguen los movimientos ni
    del reloj, lo que la hace reproducible corte a corte.
    """
    por_cliente: dict[str, list[Movimiento]] = {}
    for mov in movimientos:
        por_cliente.setdefault(mov.cliente_nit, []).append(mov)

    resultado: list[Movimiento] = []
    rastros: list[AplicacionCredito] = []

    for nit in sorted(por_cliente):
        netos, rastro = _aplicar_a_cliente(nit, por_cliente[nit])
        resultado.extend(netos)
        if rastro is not None:
            rastros.append(rastro)

    return resultado, rastros


def _aplicar_a_cliente(
    nit: str, movimientos: Sequence[Movimiento]
) -> tuple[list[Movimiento], AplicacionCredito | None]:
    credito_total = monto(sum((m.valor_credito for m in movimientos), CERO))
    if credito_total <= CERO:
        return list(movimientos), None

    # De la mas antigua a la mas reciente. El orden es explicito y no el de
    # llegada, para que dos corridas del mismo corte apliquen igual.
    ordenados = sorted(movimientos, key=lambda m: m.orden_antiguedad)

    restante = credito_total
    aplicaciones: list[tuple[str, Decimal]] = []
    netos: list[Movimiento] = []

    for mov in ordenados:
        aplicado = min(restante, mov.saldo) if mov.saldo > CERO else CERO
        if aplicado > CERO:
            aplicaciones.append((mov.factura, aplicado))
            restante = monto(restante - aplicado)
        netos.append(
            replace(
                mov,
                saldo=monto(mov.saldo - aplicado),
                saldo_bruto=mov.saldo,
                credito_aplicado=aplicado,
            )
        )

    return netos, AplicacionCredito(
        cliente_nit=nit,
        credito_total=credito_total,
        aplicaciones=tuple(aplicaciones),
        no_aplicado=restante,
    )
