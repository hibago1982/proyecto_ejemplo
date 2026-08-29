"""C-10: aplicacion de notas credito y abonos a la factura mas antigua."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from busint_alertas.core.motor import ContextoEjecucion
from busint_alertas.motores.cartera import ConfiguracionCartera, Movimiento, MotorCartera
from busint_alertas.motores.cartera.creditos import aplicar_creditos

from ..conftest import CORTE, EMPRESA


def fac(numero, dias_vencida, saldo, credito="0", nit="900", plazo=30):
    vencimiento = CORTE - timedelta(days=dias_vencida)
    return Movimiento(
        empresa_id=EMPRESA,
        cliente_nit=nit,
        factura=numero,
        fecha_emision=vencimiento - timedelta(days=plazo),
        fecha_vencimiento=vencimiento,
        saldo=Decimal(saldo),
        valor_credito=Decimal(credito),
    )


def saldos(movimientos):
    return {m.factura: m.saldo for m in movimientos}


class TestAplicacionBasica:
    def test_el_credito_va_a_la_factura_mas_antigua(self):
        movs = [
            fac("F-nueva", 10, "1000000"),
            fac("F-vieja", 90, "1000000", credito="400000"),
        ]
        netos, _ = aplicar_creditos(movs)
        assert saldos(netos) == {
            "F-vieja": Decimal("600000.00"),
            "F-nueva": Decimal("1000000.00"),
        }

    def test_el_credito_no_pertenece_a_la_fila_en_que_viaja(self):
        """Viene en la fila de la factura nueva pero se aplica a la antigua."""
        movs = [
            fac("F-vieja", 90, "1000000"),
            fac("F-nueva", 10, "1000000", credito="300000"),
        ]
        netos, _ = aplicar_creditos(movs)
        assert saldos(netos)["F-vieja"] == Decimal("700000.00")
        assert saldos(netos)["F-nueva"] == Decimal("1000000.00")

    def test_sin_credito_los_saldos_no_cambian(self):
        movs = [fac("F-1", 10, "1000000"), fac("F-2", 50, "2000000")]
        netos, rastros = aplicar_creditos(movs)
        assert saldos(netos) == {"F-1": Decimal("1000000.00"), "F-2": Decimal("2000000.00")}
        assert rastros == []

    def test_se_conserva_el_saldo_bruto_para_auditoria(self):
        movs = [fac("F-1", 90, "1000000", credito="400000")]
        neto = aplicar_creditos(movs)[0][0]
        assert neto.saldo == Decimal("600000.00")
        assert neto.saldo_bruto == Decimal("1000000.00")
        assert neto.credito_aplicado == Decimal("400000.00")


class TestCascada:
    """La regla dice "la mas antigua", pero un credito mayor tiene que ir a algun lado."""

    def test_el_remanente_pasa_a_la_siguiente_mas_antigua(self):
        movs = [
            fac("F-1", 90, "1000000", credito="2500000"),
            fac("F-2", 60, "1000000"),
            fac("F-3", 30, "1000000"),
        ]
        netos, _ = aplicar_creditos(movs)
        assert saldos(netos) == {
            "F-1": Decimal("0.00"),
            "F-2": Decimal("0.00"),
            "F-3": Decimal("500000.00"),
        }

    def test_los_creditos_de_varias_filas_se_suman(self):
        movs = [
            fac("F-1", 90, "1000000", credito="300000"),
            fac("F-2", 60, "1000000", credito="200000"),
        ]
        netos, rastro = aplicar_creditos(movs)
        assert rastro[0].credito_total == Decimal("500000.00")
        assert saldos(netos)["F-1"] == Decimal("500000.00")
        assert saldos(netos)["F-2"] == Decimal("1000000.00")


class TestSobranteYBordes:
    def test_un_credito_mayor_que_toda_la_cartera_no_produce_saldo_negativo(self):
        movs = [fac("F-1", 90, "1000000", credito="1500000")]
        netos, rastro = aplicar_creditos(movs)
        assert netos[0].saldo == Decimal("0.00")
        assert rastro[0].no_aplicado == Decimal("500000.00")

    def test_el_credito_exacto_deja_la_factura_en_cero_sin_sobrante(self):
        movs = [fac("F-1", 90, "1000000", credito="1000000")]
        netos, rastro = aplicar_creditos(movs)
        assert netos[0].saldo == Decimal("0.00")
        assert rastro[0].no_aplicado == Decimal("0.00")

    def test_el_credito_de_un_cliente_no_toca_a_otro(self):
        movs = [
            fac("F-A", 90, "1000000", credito="900000", nit="900"),
            fac("F-B", 90, "1000000", nit="901"),
        ]
        netos, _ = aplicar_creditos(movs)
        assert saldos(netos) == {"F-A": Decimal("100000.00"), "F-B": Decimal("1000000.00")}


class TestDeterminismo:
    def test_el_orden_de_llegada_no_altera_el_reparto(self):
        movs = [
            fac("F-1", 90, "1000000", credito="1500000"),
            fac("F-2", 60, "1000000"),
            fac("F-3", 30, "1000000"),
        ]
        directo, _ = aplicar_creditos(movs)
        invertido, _ = aplicar_creditos(list(reversed(movs)))
        assert saldos(directo) == saldos(invertido)

    def test_la_antiguedad_se_mide_por_vencimiento(self):
        """Con plazos distintos, emitir antes no es vencer antes.

        F-tardia se emitio primero pero vence despues por tener plazo mas
        largo. El credito va a la que lleva mas dias vencida.
        """
        movs = [
            fac("F-tardia", 10, "1000000", plazo=180),
            fac("F-vencida", 90, "1000000", credito="400000", plazo=30),
        ]
        netos, _ = aplicar_creditos(movs)
        assert saldos(netos)["F-vencida"] == Decimal("600000.00")
        assert saldos(netos)["F-tardia"] == Decimal("1000000.00")


class TestEfectoEnLasAlertas:
    """El saldo neto es el que llega a la alerta, que es lo que pidio el negocio."""

    def evaluar(self, movs):
        config = ConfiguracionCartera.plantilla(
            EMPRESA, dias_preventivos=5, n_facturas_vencidas=3,
            pct_mayor_90_umbral=Decimal("40"),
        )
        return MotorCartera().evaluar(
            ContextoEjecucion(EMPRESA, CORTE, config), movs
        )

    def test_la_alerta_lleva_el_saldo_neto_y_el_bruto(self):
        movs = [fac("F-1", -3, "1000000", credito="400000")]
        alerta = self.evaluar(movs).alertas[0]
        assert alerta.datos["saldo"] == Decimal("600000.00")
        assert alerta.datos["saldo_bruto"] == Decimal("1000000.00")
        assert alerta.datos["credito_aplicado"] == Decimal("400000.00")

    def test_los_indicadores_usan_el_saldo_neto(self):
        movs = [fac("F-1", 45, "1000000", credito="400000")]
        g = self.evaluar(movs).indicadores["globales"]
        assert g["cartera_total"] == Decimal("600000.00")

    def test_una_factura_saldada_no_genera_alerta(self):
        """Cobrar cero es ruido: la factura quedo cubierta por el credito."""
        movs = [
            fac("F-1", 90, "1000000", credito="1000000"),
            fac("F-2", 60, "1000000"),
            fac("F-3", 30, "1000000"),
        ]
        resultado = self.evaluar(movs)
        assert not any(a.codigo == "A10" for a in resultado.alertas)
        assert resultado.indicadores["clientes"]["900"].n_vencidas == 2

    def test_la_factura_saldada_queda_registrada(self):
        movs = [fac("F-1", 90, "1000000", credito="1000000")]
        saldadas = self.evaluar(movs).indicadores["facturas_saldadas_por_credito"]
        assert saldadas == [("900", "F-1", Decimal("1000000.00"))]

    def test_el_credito_sobrante_se_reporta_aparte(self):
        """Solo sobra credito cuando cubre toda la cartera del cliente.

        En ese caso el cliente se queda sin facturas abiertas y sin perfil, asi
        que su saldo a favor tiene que reportarse fuera de la lista de clientes
        o se perderia.
        """
        movs = [
            fac("F-1", 90, "1000000", credito="2400000"),
            fac("F-2", 30, "1000000"),
        ]
        resultado = self.evaluar(movs)
        assert resultado.indicadores["creditos_a_favor"] == [("900", Decimal("400000.00"))]
        assert "900" not in resultado.indicadores["clientes"]

    def test_un_cliente_con_cartera_abierta_no_deja_credito_a_favor(self):
        movs = [
            fac("F-1", 90, "1000000", credito="1400000"),
            fac("F-2", 30, "1000000"),
        ]
        resultado = self.evaluar(movs)
        assert resultado.indicadores["creditos_a_favor"] == []
        assert resultado.indicadores["clientes"]["900"].cartera_total == Decimal("600000.00")

    def test_el_credito_puede_desactivar_una_alerta_de_umbral(self):
        """Bajar el saldo cambia el porcentaje de concentracion y apaga A11."""
        sin_credito = [
            fac("F-1", 120, "600000", nit="900"),
            fac("F-2", 10, "400000", nit="900"),
        ]
        assert any(a.codigo == "A11" for a in self.evaluar(sin_credito).alertas)

        # El credito va a la factura de mas de 90 dias, que es la mas antigua,
        # asi que baja numerador y denominador a la vez: 200k sobre 600k.
        con_credito = [
            fac("F-1", 120, "600000", credito="400000", nit="900"),
            fac("F-2", 10, "400000", nit="900"),
        ]
        assert not any(a.codigo == "A11" for a in self.evaluar(con_credito).alertas)


class TestRastroAuditable:
    def test_el_rastro_dice_a_que_facturas_fue_el_credito(self):
        movs = [
            fac("F-1", 90, "1000000", credito="1500000"),
            fac("F-2", 60, "1000000"),
        ]
        rastro = aplicar_creditos(movs)[1][0]
        assert rastro.credito_total == Decimal("1500000.00")
        assert rastro.aplicaciones == (
            ("F-1", Decimal("1000000.00")),
            ("F-2", Decimal("500000.00")),
        )
        assert rastro.facturas_saldadas == ("F-1", "F-2")
        assert "F-1: 1000000.00" in str(rastro)
