"""Configuracion en base: §8.4 parametrizar sin tocar codigo, §10.3 auditoria."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from busint_alertas.core.tipos import Prioridad
from busint_alertas.ejecucion import ejecutar_corte
from busint_alertas.motores.cartera import Movimiento
from busint_alertas.persistencia import configuracion as config_bd
from busint_alertas.persistencia.modelo import AgingParam, AlertRule, AuditoriaConfig

from .conftest import EMPRESA
from .test_reproceso import CORTE, FuenteFalsa, factura


class TestSiembra:
    def test_deja_los_ocho_buckets_de_52(self, sesion_sembrada):
        filas = sesion_sembrada.scalars(
            select(AgingParam).order_by(AgingParam.orden)
        ).all()
        assert [f.codigo for f in filas] == [f"B0{i}" for i in range(8)]
        assert [f.alerta for f in filas] == [
            None, "A02", "A03", "A04", "A05", "A06", "A07", "A08"
        ]

    def test_no_inventa_umbrales_monetarios(self, sesion_sembrada):
        """§16: no usar la base de demostracion para fijar umbrales reales."""
        reglas = {
            r.codigo: r.parametros
            for r in sesion_sembrada.scalars(select(AlertRule))
        }
        assert reglas["R01"] == {}
        assert reglas["R02"] == {}

    def test_sembrar_dos_veces_no_duplica(self, sesion_sembrada):
        config_bd.sembrar(sesion_sembrada, EMPRESA, dias_preventivos=15)
        assert len(sesion_sembrada.scalars(select(AgingParam)).all()) == 8

    def test_la_configuracion_cargada_reproduce_los_buckets(self, sesion_sembrada):
        config = config_bd.cargar(sesion_sembrada, EMPRESA)
        assert config.buckets.asignar(0).codigo == "B01"
        assert config.buckets.asignar(45).codigo == "B03"
        assert config.buckets.asignar(999).codigo == "B07"
        assert config.buckets.obtener("B05").prioridad_base is Prioridad.MUY_ALTA

    def test_una_empresa_sin_sembrar_lo_dice(self, sesion):
        with pytest.raises(LookupError, match="no tiene buckets configurados"):
            config_bd.cargar(sesion, "E99")


class TestActivacionDeR01YR02:
    """R01 y R02 nacen inactivas y se encienden cuando la empresa fija el umbral.

    Es la decision de negocio confirmada: no se activan por despliegue, se
    activan por configuracion.
    """

    CARTERA = [factura("F-1", 45, saldo="8000000")]

    def test_sin_umbral_quedan_inactivas(self, sesion_sembrada):
        corrida = ejecutar_corte(
            sesion_sembrada, FuenteFalsa(self.CARTERA), EMPRESA, CORTE
        )
        assert "R01" in corrida.resultado.reglas_inactivas
        assert "R02" in corrida.resultado.reglas_inactivas
        assert not any(a.codigo == "A09" for a in corrida.resultado.alertas)

    def test_al_fijar_el_umbral_r01_empieza_a_elevar_la_prioridad(
        self, sesion_sembrada
    ):
        antes = ejecutar_corte(
            sesion_sembrada, FuenteFalsa(self.CARTERA), EMPRESA, CORTE
        )
        a04_antes = next(a for a in antes.resultado.alertas if a.codigo == "A04")
        assert a04_antes.prioridad is Prioridad.ALTA

        config_bd.fijar_parametro(
            sesion_sembrada, EMPRESA, "R01", "umbral_saldo_alto", 5000000, "admin"
        )

        despues = ejecutar_corte(
            sesion_sembrada, FuenteFalsa(self.CARTERA), EMPRESA,
            CORTE + timedelta(days=1),
        )
        assert "R01" not in despues.resultado.reglas_inactivas
        a04 = next(a for a in despues.resultado.alertas if a.codigo == "A04")
        assert a04.prioridad is Prioridad.MUY_ALTA

    def test_al_fijar_el_umbral_critico_aparece_a09(self, sesion_sembrada):
        config_bd.fijar_parametro(
            sesion_sembrada, EMPRESA, "R02", "umbral_saldo_critico", 5000000, "admin"
        )
        corrida = ejecutar_corte(
            sesion_sembrada, FuenteFalsa(self.CARTERA), EMPRESA, CORTE
        )
        assert "R02" not in corrida.resultado.reglas_inactivas
        assert any(a.codigo == "A09" for a in corrida.resultado.alertas)

    def test_no_hizo_falta_tocar_codigo(self, sesion_sembrada):
        """La activacion es un UPDATE en ar_alert_rule, no un despliegue."""
        regla = sesion_sembrada.scalar(
            select(AlertRule).where(AlertRule.codigo == "R01")
        )
        assert regla.parametros == {}
        config_bd.fijar_parametro(
            sesion_sembrada, EMPRESA, "R01", "umbral_saldo_alto", 5000000, "admin"
        )
        assert regla.parametros == {"umbral_saldo_alto": "5000000"}


class TestAuditoria:
    """§10.3: quien cambio que, cuando, y de que valor a cual."""

    def test_el_cambio_queda_registrado(self, sesion_sembrada):
        config_bd.fijar_parametro(
            sesion_sembrada, EMPRESA, "R03", "n_facturas_vencidas", 5, "hbarrera"
        )
        fila = sesion_sembrada.scalars(select(AuditoriaConfig)).one()
        assert fila.usuario_id == "hbarrera"
        assert fila.entidad == "ar_alert_rule.R03"
        assert fila.campo == "n_facturas_vencidas"
        assert fila.valor_anterior == "3"
        assert fila.valor_nuevo == "5"

    def test_fijar_un_umbral_por_primera_vez_deja_el_anterior_vacio(
        self, sesion_sembrada
    ):
        config_bd.fijar_parametro(
            sesion_sembrada, EMPRESA, "R01", "umbral_saldo_alto", 5000000, "hbarrera"
        )
        fila = sesion_sembrada.scalars(select(AuditoriaConfig)).one()
        assert fila.valor_anterior is None
        assert fila.valor_nuevo == "5000000"

    def test_una_regla_inexistente_lo_dice(self, sesion_sembrada):
        with pytest.raises(LookupError, match="No existe la regla 'R99'"):
            config_bd.fijar_parametro(
                sesion_sembrada, EMPRESA, "R99", "x", 1, "admin"
            )
