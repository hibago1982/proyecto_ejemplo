"""Indicadores de §6, identidad C-14 y aislamiento multiempresa C-08."""

from __future__ import annotations

from decimal import Decimal

from busint_alertas.core.motor import ContextoEjecucion
from busint_alertas.motores.cartera import MotorCartera

from ..conftest import CORTE, EMPRESA, factura


def evaluar(config, movimientos, empresa=EMPRESA):
    return MotorCartera().evaluar(
        ContextoEjecucion(empresa_id=empresa, corte=CORTE, configuracion=config),
        movimientos,
    )


class TestIdentidadDeCartera:
    """C-14: cartera total = por vencer + vence hoy + vencida."""

    def test_las_tres_partes_suman_el_total(self, config_completa):
        movs = [
            factura(dias_vencida=-10, saldo="100000", numero="F-1"),
            factura(dias_vencida=0, saldo="200000", numero="F-2"),
            factura(dias_vencida=45, saldo="300000", numero="F-3"),
        ]
        g = evaluar(config_completa, movs).indicadores["globales"]
        assert g["por_vencer"] == Decimal("100000.00")
        assert g["vence_hoy"] == Decimal("200000.00")
        assert g["vencida"] == Decimal("300000.00")
        assert g["cartera_total"] == Decimal("600000.00")

    def test_vence_hoy_no_se_suma_a_vencida(self, config_completa):
        g = evaluar(config_completa, [factura(dias_vencida=0, saldo="500000")]).indicadores["globales"]
        assert g["vencida"] == Decimal("0.00")
        assert g["vence_hoy"] == Decimal("500000.00")
        assert g["cartera_total"] == Decimal("500000.00")

    def test_la_identidad_se_cumple_tambien_por_cliente(self, config_completa):
        movs = [
            factura(dias_vencida=-5, saldo="100000", numero="F-1", nit="900"),
            factura(dias_vencida=0, saldo="150000", numero="F-2", nit="900"),
            factura(dias_vencida=200, saldo="250000", numero="F-3", nit="900"),
        ]
        perfil = evaluar(config_completa, movs).indicadores["clientes"]["900"]
        assert perfil.por_vencer + perfil.vence_hoy + perfil.vencida == perfil.cartera_total
        assert perfil.cartera_total == Decimal("500000.00")


class TestCortesDeNoventaYCientoCincuenta:
    def test_mayor_90_y_mayor_150_son_estrictos(self, config_completa):
        movs = [
            factura(dias_vencida=90, saldo="100000", numero="F-1"),
            factura(dias_vencida=91, saldo="200000", numero="F-2"),
            factura(dias_vencida=150, saldo="400000", numero="F-3"),
            factura(dias_vencida=151, saldo="800000", numero="F-4"),
        ]
        g = evaluar(config_completa, movs).indicadores["globales"]
        assert g["mayor_90"] == Decimal("1400000.00")
        assert g["mayor_150"] == Decimal("800000.00")

    def test_porcentajes_con_dos_decimales(self, config_completa):
        movs = [
            factura(dias_vencida=120, saldo="100000", numero="F-1"),
            factura(dias_vencida=-5, saldo="200000", numero="F-2"),
        ]
        g = evaluar(config_completa, movs).indicadores["globales"]
        assert g["pct_90"] == Decimal("33.33")


class TestAislamientoMultiempresa:
    """C-08: empresa_id es dimension de aislamiento, no un campo informativo."""

    def test_no_se_mezclan_empresas_en_un_corte(self, config_completa):
        movs = [
            factura(dias_vencida=10, saldo="100000", numero="F-1", empresa="E01"),
            factura(dias_vencida=10, saldo="999999", numero="F-2", empresa="E02"),
        ]
        g = evaluar(config_completa, movs, empresa="E01").indicadores["globales"]
        assert g["cartera_total"] == Decimal("100000.00")
        assert g["n_facturas"] == 1


class TestDeterminismo:
    """§4.2: misma entrada, misma salida. Es la base de C-16."""

    def test_dos_corridas_dan_el_mismo_resultado(self, config_completa):
        movs = [factura(dias_vencida=d, numero=f"F-{d}") for d in (-5, 0, 15, 95, 200)]
        primera = evaluar(config_completa, movs).indicadores["globales"]
        segunda = evaluar(config_completa, movs).indicadores["globales"]
        assert primera == segunda

    def test_el_orden_de_entrada_no_altera_los_indicadores(self, config_completa):
        movs = [factura(dias_vencida=d, numero=f"F-{d}") for d in (-5, 0, 15, 95, 200)]
        directo = evaluar(config_completa, movs).indicadores["globales"]
        invertido = evaluar(config_completa, list(reversed(movs))).indicadores["globales"]
        assert directo == invertido
