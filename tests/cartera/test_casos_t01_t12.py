"""Casos de prueba minimos T01-T12 de §14.

Son los que la especificacion define como entregable verificable de la fase 1.
Cada prueba lleva el enunciado literal del documento para que la trazabilidad
sea comprobable sin abrirlo.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from busint_alertas.core.motor import ContextoEjecucion
from busint_alertas.core.tipos import Prioridad
from busint_alertas.motores.cartera import ConfiguracionCartera, Movimiento, MotorCartera

from ..conftest import CORTE, EMPRESA


def factura(dias, saldo="1000000", numero="F-1", nit="900"):
    venc = CORTE - timedelta(days=dias)
    return Movimiento(
        empresa_id=EMPRESA, cliente_nit=nit, factura=numero,
        fecha_emision=venc - timedelta(days=30), fecha_vencimiento=venc,
        saldo=Decimal(saldo),
    )


@pytest.fixture
def config():
    """Umbrales de prueba. §16: no salen de la base de demostracion."""
    return ConfiguracionCartera.plantilla(
        EMPRESA,
        dias_preventivos=15,
        n_facturas_vencidas=3,
        pct_mayor_90_umbral=Decimal("40"),
        umbral_saldo_alto=Decimal("5000000"),
        umbral_saldo_critico=Decimal("20000000"),
    )


def evaluar(config, movs):
    return MotorCartera().evaluar(
        ContextoEjecucion(EMPRESA, CORTE, config), movs
    )


def alertas_de(resultado, factura):
    return {a.codigo for a in resultado.alertas if a.entidad == factura}


def bucket_de(resultado, factura):
    return next(
        a.datos["bucket"] for a in resultado.alertas if a.entidad == factura
    )


class TestCasosDeAntiguedad:
    """T01-T08: cada rango de dias recibe la alerta que le corresponde."""

    @pytest.mark.parametrize(
        "caso, dias, bucket, alerta",
        [
            ("T02 Factura vence hoy", 0, "B01", "A02"),
            ("T03 Factura 15 dias vencida", 15, "B02", "A03"),
            ("T04 Factura 45 dias vencida", 45, "B03", "A04"),
            ("T05 Factura 80 dias vencida", 80, "B04", "A05"),
            ("T06 Factura 100 dias vencida", 100, "B05", "A06"),
            ("T07 Factura 140 dias vencida", 140, "B06", "A07"),
            ("T08 Factura 200 dias vencida", 200, "B07", "A08"),
        ],
    )
    def test_rango_y_alerta(self, config, caso, dias, bucket, alerta):
        resultado = evaluar(config, [factura(dias)])
        assert bucket_de(resultado, "F-1") == bucket, caso
        assert alerta in alertas_de(resultado, "F-1"), caso

    def test_t01_factura_vence_en_10_dias(self, config):
        """T01: -10 dias -> Por vencer, A01 si aplica.

        Con ventana preventiva de 15 dias, aplica.
        """
        resultado = evaluar(config, [factura(-10)])
        assert alertas_de(resultado, "F-1") == {"A01"}

    def test_t01_fuera_de_la_ventana_no_genera_alerta(self, config):
        """El "si aplica" del enunciado: por vencer no siempre alerta."""
        resultado = evaluar(config, [factura(-40)])
        assert resultado.alertas == []
        g = resultado.indicadores["globales"]
        assert g["por_vencer"] == Decimal("1000000.00")


class TestT09SaldoNegativo:
    """T09: saldo negativo a 200 dias -> credito/saldo no deudor, no mora."""

    def test_no_se_clasifica_como_mora(self, config):
        resultado = evaluar(config, [factura(200, saldo="-500000")])
        assert resultado.alertas == []
        assert resultado.indicadores["globales"]["vencida"] == Decimal("0.00")

    def test_se_reporta_como_credito_a_favor(self, config):
        resultado = evaluar(config, [factura(200, saldo="-500000")])
        assert resultado.indicadores["saldos_no_deudores"] == [
            ("900", "F-1", Decimal("-500000.00"), "credito_a_favor")
        ]

    def test_un_saldo_cero_se_distingue_del_credito_a_favor(self, config):
        """§5.3 pide diferenciar los tres estados, no solo dos."""
        resultado = evaluar(config, [factura(200, saldo="0")])
        assert resultado.indicadores["saldos_no_deudores"] == [
            ("900", "F-1", Decimal("0.00"), "saldo_cero")
        ]

    def test_no_cuenta_como_factura_vencida_del_cliente(self, config):
        """§6: el conteo es de facturas con dias > 0 y saldo deudor."""
        movs = [
            factura(200, saldo="-500000", numero="F-1"),
            factura(100, saldo="1000000", numero="F-2"),
        ]
        perfil = evaluar(config, movs).indicadores["clientes"]["900"]
        assert perfil.n_vencidas == 1


class TestT10ClienteConVariasFacturas:
    """T10: facturas a 31, 95 y 180 dias -> maxima prioridad aplicable."""

    def movimientos(self):
        return [
            factura(31, numero="F-31"),
            factura(95, numero="F-95"),
            factura(180, numero="F-180"),
        ]

    def test_cada_factura_recibe_su_alerta(self, config):
        resultado = evaluar(config, self.movimientos())
        assert alertas_de(resultado, "F-31") == {"A04"}
        assert alertas_de(resultado, "F-95") == {"A06"}
        assert alertas_de(resultado, "F-180") == {"A08"}

    def test_la_prioridad_del_cliente_es_la_maxima_aplicable(self, config):
        perfil = evaluar(config, self.movimientos()).indicadores["clientes"]["900"]
        assert perfil.prioridad is Prioridad.CRITICA

    def test_se_marcan_los_dos_riesgos_de_cliente(self, config):
        """R04 por pasar de 90 dias y R05 por pasar de 150."""
        resultado = evaluar(config, self.movimientos())
        assert {m.codigo for m in resultado.marcadores} == {"M04", "M05"}

    def test_el_cliente_es_reincidente(self, config):
        """Tres facturas vencidas con N=3 disparan A10 (C-02)."""
        resultado = evaluar(config, self.movimientos())
        assert any(a.codigo == "A10" for a in resultado.alertas)


class TestT11SaldoAltoMas45Dias:
    """T11: saldo alto y 45 dias -> 31-60 mas alta exposicion, elevar prioridad."""

    def test_r01_eleva_la_prioridad_del_bucket(self, config):
        """B03 tiene prioridad base Alta; con R01 sube a Muy alta."""
        resultado = evaluar(config, [factura(45, saldo="8000000")])
        a04 = next(a for a in resultado.alertas if a.codigo == "A04")
        assert a04.datos["prioridad_base"] == "Alta"
        assert a04.prioridad is Prioridad.MUY_ALTA

    def test_la_elevacion_queda_explicada(self, config):
        """§7.4: hay que poder mostrar que regla elevo la prioridad."""
        resultado = evaluar(config, [factura(45, saldo="8000000")])
        a04 = next(a for a in resultado.alertas if a.codigo == "A04")
        assert any("R01" in e for e in a04.datos["elevada_por"])
        assert any("umbral_saldo_alto" in e for e in a04.datos["elevada_por"])

    def test_r01_no_aplica_con_30_dias_o_menos(self, config):
        """§5.4 exige las dos condiciones: umbral monetario y dias > 30."""
        resultado = evaluar(config, [factura(30, saldo="8000000")])
        a03 = next(a for a in resultado.alertas if a.codigo == "A03")
        assert a03.prioridad is Prioridad.MEDIA
        assert a03.datos["elevada_por"] == []

    def test_el_umbral_critico_emite_a09(self, config):
        resultado = evaluar(config, [factura(45, saldo="25000000")])
        assert "A09" in alertas_de(resultado, "F-1")

    def test_a09_no_exige_estar_vencida(self, config):
        """§5.4 no le repite a R02 la condicion de dias que si lleva R01."""
        resultado = evaluar(config, [factura(-3, saldo="25000000")])
        assert "A09" in alertas_de(resultado, "F-1")


class TestT12Reproceso:
    """T12: reprocesar el mismo corte da el mismo resultado, sin duplicados."""

    def movimientos(self):
        return [factura(d, numero=f"F-{d}") for d in (-10, 0, 15, 45, 100, 200)]

    def test_dos_corridas_producen_las_mismas_alertas(self, config):
        primera = evaluar(config, self.movimientos())
        segunda = evaluar(config, self.movimientos())
        clave = lambda r: sorted((a.codigo, a.sujeto, a.entidad) for a in r.alertas)
        assert clave(primera) == clave(segunda)

    def test_no_hay_alertas_duplicadas_en_una_corrida(self, config):
        resultado = evaluar(config, self.movimientos())
        claves = [(a.codigo, a.sujeto, a.entidad) for a in resultado.alertas]
        assert len(claves) == len(set(claves))
