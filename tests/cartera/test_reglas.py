"""Reglas activas y politica de reglas inactivas."""

from __future__ import annotations

from decimal import Decimal

import pytest

from busint_alertas.core.motor import ContextoEjecucion
from busint_alertas.core.tipos import Fase, Prioridad
from busint_alertas.motores.cartera import ConfiguracionCartera, MotorCartera

from ..conftest import CORTE, EMPRESA, factura


def evaluar(config, movimientos, fase=Fase.F1_MOTOR):
    contexto = ContextoEjecucion(
        empresa_id=EMPRESA, corte=CORTE, configuracion=config, fase_vigente=fase
    )
    return MotorCartera().evaluar(contexto, movimientos)


class TestR03FacturasVencidas:
    """C-02: se adopta 'N o mas' (>=), criterio de A10, no 'mas de N'."""

    def _cliente_con(self, n_vencidas):
        return [
            factura(dias_vencida=10, numero=f"F-{i}", nit="900")
            for i in range(n_vencidas)
        ]

    def test_exactamente_n_dispara(self, config_completa):
        """El caso que distinguia las dos redacciones: N=3 y 3 facturas."""
        resultado = evaluar(config_completa, self._cliente_con(3))
        assert any(a.codigo == "A10" for a in resultado.alertas)

    def test_menos_de_n_no_dispara(self, config_completa):
        resultado = evaluar(config_completa, self._cliente_con(2))
        assert not any(a.codigo == "A10" for a in resultado.alertas)

    def test_mas_de_n_dispara(self, config_completa):
        resultado = evaluar(config_completa, self._cliente_con(5))
        assert any(a.codigo == "A10" for a in resultado.alertas)

    def test_las_facturas_por_vencer_no_cuentan_como_vencidas(self, config_completa):
        movs = self._cliente_con(2) + [factura(dias_vencida=-3, numero="F-X", nit="900")]
        resultado = evaluar(config_completa, movs)
        assert not any(a.codigo == "A10" for a in resultado.alertas)

    def test_la_alerta_es_de_cliente_y_no_de_factura(self, config_completa):
        resultado = evaluar(config_completa, self._cliente_con(3))
        a10 = next(a for a in resultado.alertas if a.codigo == "A10")
        assert a10.sujeto == "900"
        assert a10.entidad is None


class TestR06Preventiva:
    """C-03 y C-06: A01 con prioridad Media y parametro `dias_preventivos`."""

    def test_dentro_de_la_ventana_dispara(self, config_completa):
        resultado = evaluar(config_completa, [factura(dias_vencida=-3)])
        assert [a.codigo for a in resultado.alertas] == ["A01"]

    def test_en_el_limite_de_la_ventana_dispara(self, config_completa):
        resultado = evaluar(config_completa, [factura(dias_vencida=-5)])
        assert [a.codigo for a in resultado.alertas] == ["A01"]

    def test_fuera_de_la_ventana_no_dispara(self, config_completa):
        resultado = evaluar(config_completa, [factura(dias_vencida=-6)])
        assert resultado.alertas == []

    def test_el_dia_del_vencimiento_es_a02_y_no_a01(self, config_completa):
        """§7 separa A01 de A02, y §14 lo confirma con T01 y T02.

        Antes de tener la especificacion la ventana incluia dias=0; era una
        suposicion, y era incorrecta.
        """
        resultado = evaluar(config_completa, [factura(dias_vencida=0)])
        assert [a.codigo for a in resultado.alertas] == ["A02"]

    def test_una_factura_vencida_no_es_preventiva(self, config_completa):
        resultado = evaluar(config_completa, [factura(dias_vencida=1)])
        assert not any(a.codigo == "A01" for a in resultado.alertas)

    def test_la_prioridad_es_media(self, config_completa):
        """C-03: A01 aparecia como 'Informativa/Media' sin resolver cual."""
        resultado = evaluar(config_completa, [factura(dias_vencida=-3)])
        assert resultado.alertas[0].prioridad is Prioridad.MEDIA


class TestA11Concentracion:
    def test_supera_el_umbral(self, config_completa):
        movs = [
            factura(dias_vencida=120, saldo="600000", numero="F-1", nit="900"),
            factura(dias_vencida=10, saldo="400000", numero="F-2", nit="900"),
        ]
        resultado = evaluar(config_completa, movs)
        a11 = next(a for a in resultado.alertas if a.codigo == "A11")
        assert a11.explicacion.valor_observado == Decimal("60.00")

    def test_justo_en_el_umbral_no_dispara(self, config_completa):
        """El operador es estrictamente mayor: 40% con umbral 40 no dispara."""
        movs = [
            factura(dias_vencida=120, saldo="400000", numero="F-1", nit="900"),
            factura(dias_vencida=10, saldo="600000", numero="F-2", nit="900"),
        ]
        resultado = evaluar(config_completa, movs)
        assert not any(a.codigo == "A11" for a in resultado.alertas)


class TestReglasInactivas:
    def test_sin_parametro_la_regla_no_se_evalua(self):
        """C-05: el motor no asume ningun valor por defecto."""
        config = ConfiguracionCartera.plantilla(EMPRESA, dias_preventivos=5)
        resultado = evaluar(config, [factura(dias_vencida=10, numero=f"F-{i}")
                                     for i in range(9)])
        assert "R03" in resultado.reglas_inactivas
        assert "n_facturas_vencidas" in resultado.reglas_inactivas["R03"]
        assert not any(a.codigo == "A10" for a in resultado.alertas)

    def test_a12_no_se_evalua_antes_de_la_fase_5(self, config_completa):
        """C-07: sin historial de gestion, A12 se dispararia siempre."""
        resultado = evaluar(config_completa, [factura(dias_vencida=10)])
        assert "A12" in resultado.reglas_inactivas

    def test_las_reglas_de_54_ya_tienen_condicion(self, config_completa):
        """Ninguna regla de §5.4 queda sin evaluador."""
        from busint_alertas.motores.cartera.reglas import REGLAS

        for regla in REGLAS:
            if regla.codigo == "A12":
                continue  # fase 5, depende del historial de gestion
            assert regla.evaluar is not None, regla.codigo

    def test_r01_y_r02_sin_umbral_quedan_inactivas(self, config_completa):
        """C-05: los umbrales monetarios los fija la empresa, no el programador.

        §16 lo dice ademas de forma expresa: no usar la base de demostracion
        para definir umbrales monetarios reales.
        """
        resultado = evaluar(config_completa, [factura(dias_vencida=45)])
        for codigo in ("R01", "R02"):
            assert codigo in resultado.reglas_inactivas
            assert "no ha asignado valor" in resultado.reglas_inactivas[codigo]

    def test_una_regla_activa_no_aparece_como_inactiva(self, config_completa):
        resultado = evaluar(config_completa, [factura(dias_vencida=10)])
        assert "R03" not in resultado.reglas_inactivas
        assert "R06" not in resultado.reglas_inactivas


class TestExplicabilidad:
    """§7.4: toda alerta debe poder mostrar por que se disparo."""

    def test_la_alerta_lleva_regla_parametro_y_valor(self, config_completa):
        movs = [factura(dias_vencida=10, numero=f"F-{i}", nit="900") for i in range(4)]
        resultado = evaluar(config_completa, movs)
        exp = next(a for a in resultado.alertas if a.codigo == "A10").explicacion
        assert exp.regla == "R03"
        assert exp.parametro == "n_facturas_vencidas"
        assert exp.valor_parametro == 3
        assert exp.valor_observado == 4
        assert "4 facturas vencidas" in str(exp)
