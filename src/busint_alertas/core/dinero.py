"""Politica de moneda y redondeo (C-09).

Pesos colombianos. Se almacena y se calcula con dos decimales; el redondeo a
enteros se aplica unicamente en presentacion, nunca en el calculo ni en la
exportacion de auditoria. Por eso `presentar` es la unica funcion que redondea
a cero decimales, y no la usa ninguna regla.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

MONEDA = "COP"
CENTAVOS = Decimal("0.01")


def monto(valor: object) -> Decimal:
    """Normaliza cualquier entrada numerica a un Decimal de dos decimales.

    Se pasa por `str` deliberadamente: `Decimal(0.1)` arrastra el error binario
    del float, `Decimal("0.1")` no.
    """
    if isinstance(valor, Decimal):
        crudo = valor
    else:
        crudo = Decimal(str(valor))
    return crudo.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def presentar(valor: Decimal) -> int:
    """Redondea a pesos enteros. Solo para mostrar en pantalla o en el PDF."""
    return int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def porcentaje(parte: Decimal, total: Decimal) -> Decimal:
    """Porcentaje con dos decimales. Devuelve 0 si el total es cero."""
    if total == 0:
        return Decimal("0.00")
    return (parte / total * Decimal(100)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
