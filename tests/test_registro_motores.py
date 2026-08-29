"""El registro es lo que permite sumar motores sin tocar API ni planificador."""

from __future__ import annotations

import pytest

from busint_alertas.core.motor import MotorAlertas, RegistroMotores
from busint_alertas.motores import registrar_motores, registro
from busint_alertas.motores.cartera import MotorCartera


def test_cartera_queda_registrada():
    registrar_motores()
    assert "cartera" in registro.codigos()
    assert isinstance(registro.obtener("cartera"), MotorCartera)


def test_registrar_motores_es_idempotente():
    registrar_motores()
    registrar_motores()
    assert registro.codigos().count("cartera") == 1


def test_el_motor_de_cartera_cumple_el_contrato():
    assert isinstance(MotorCartera(), MotorAlertas)


def test_no_se_admiten_dos_motores_con_el_mismo_codigo():
    propio = RegistroMotores()
    propio.registrar(MotorCartera())
    with pytest.raises(ValueError, match="Ya existe un motor"):
        propio.registrar(MotorCartera())


def test_pedir_un_motor_inexistente_dice_cuales_hay():
    propio = RegistroMotores()
    propio.registrar(MotorCartera())
    with pytest.raises(LookupError, match="Disponibles: cartera"):
        propio.obtener("inventario")
