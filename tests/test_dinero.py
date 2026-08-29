"""C-09: moneda, decimales y politica de redondeo."""

from __future__ import annotations

from decimal import Decimal

from busint_alertas.core.dinero import monto, porcentaje, presentar


def test_los_float_no_arrastran_error_binario():
    assert monto(0.1) == Decimal("0.10")
    assert monto(1234567.891) == Decimal("1234567.89")


def test_se_almacena_con_dos_decimales():
    assert monto("1000").as_tuple().exponent == -2


def test_el_redondeo_a_pesos_es_solo_de_presentacion():
    """El calculo conserva los centavos; solo la vista los pierde."""
    valor = monto("1000.56")
    assert valor == Decimal("1000.56")
    assert presentar(valor) == 1001


def test_porcentaje_sobre_total_cero_no_falla():
    assert porcentaje(Decimal("0"), Decimal("0")) == Decimal("0.00")
