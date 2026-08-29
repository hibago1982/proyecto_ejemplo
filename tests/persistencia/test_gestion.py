"""Entregable de la etapa 6: trazabilidad completa de una cobranza.

Y la activacion de A12, que C-07 dejaba explicitamente para esta fase porque
antes se disparaba siempre.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from busint_alertas.core.tipos import EstadoAlerta, TipoGestion
from busint_alertas.ejecucion import ejecutar_corte
from busint_alertas.persistencia import RepositorioCartera
from busint_alertas.persistencia import configuracion as config_bd
from busint_alertas.persistencia.gestion import (
    ErrorDeGestion,
    NuevaGestion,
    construir_historial,
    historial_de,
    registrar,
)

from .conftest import EMPRESA
from .test_reproceso import CARTERA, CORTE, FuenteFalsa, factura


def gestion(**cambios):
    base = dict(
        cliente_nit="900", factura="F-4", usuario_id="hbarrera",
        tipo=TipoGestion.LLAMADA, resultado="Contactado",
        momento=datetime(2026, 8, 21, 10, 0),
    )
    base.update(cambios)
    return NuevaGestion(**base)


@pytest.fixture
def con_corte(sesion_sembrada):
    ejecutar_corte(sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE)
    return sesion_sembrada


class TestRegistroDeGestion:
    def test_la_gestion_queda_guardada(self, con_corte):
        fila = registrar(con_corte, EMPRESA, CORTE, gestion())
        assert fila.usuario_id == "hbarrera"
        assert fila.tipo == "llamada"
        assert fila.corte == CORTE

    def test_la_alerta_pasa_a_gestionada(self, con_corte):
        registrar(con_corte, EMPRESA, CORTE, gestion())
        alertas = RepositorioCartera(con_corte).alertas_del_corte(
            EMPRESA, CORTE, solo_activas=False
        )
        de_la_factura = [a for a in alertas if a.factura == "F-4"]
        assert de_la_factura
        assert all(a.estado == EstadoAlerta.GESTIONADA.value for a in de_la_factura)

    def test_gestionar_no_cambia_el_saldo_ni_el_bucket(self, con_corte):
        """§16: el estado de la gestion es independiente del de la factura."""
        antes = next(
            a for a in RepositorioCartera(con_corte).alertas_del_corte(EMPRESA, CORTE)
            if a.factura == "F-4"
        )
        bucket, saldo = antes.bucket, antes.saldo

        registrar(con_corte, EMPRESA, CORTE, gestion())

        despues = next(
            a for a in RepositorioCartera(con_corte).alertas_del_corte(
                EMPRESA, CORTE, solo_activas=False
            )
            if a.factura == "F-4"
        )
        assert (despues.bucket, despues.saldo) == (bucket, saldo)

    def test_gestionar_una_factura_que_no_tiene_alerta_se_rechaza(self, con_corte):
        with pytest.raises(ErrorDeGestion, match="No hay alertas de la factura"):
            registrar(con_corte, EMPRESA, CORTE, gestion(factura="F-999"))

    def test_el_historial_va_de_lo_mas_reciente_a_lo_mas_antiguo(self, con_corte):
        registrar(con_corte, EMPRESA, CORTE,
                  gestion(momento=datetime(2026, 8, 20, 9, 0), resultado="Primera"))
        registrar(con_corte, EMPRESA, CORTE,
                  gestion(momento=datetime(2026, 8, 21, 9, 0), resultado="Segunda"))
        assert [g.resultado for g in historial_de(con_corte, EMPRESA, "900")] == [
            "Segunda", "Primera",
        ]


class TestCompromisoDePago:
    def test_se_guardan_fecha_y_valor(self, con_corte):
        fila = registrar(
            con_corte, EMPRESA, CORTE,
            gestion(
                tipo=TipoGestion.ACUERDO,
                compromiso_fecha=date(2026, 9, 15),
                compromiso_valor=Decimal("500000"),
            ),
        )
        assert fila.compromiso_fecha == date(2026, 9, 15)
        assert fila.compromiso_valor == Decimal("500000")

    def test_un_compromiso_sin_valor_se_rechaza(self, con_corte):
        """Media promesa no es un compromiso: no se puede hacer seguimiento."""
        with pytest.raises(ErrorDeGestion, match="Falta el valor"):
            registrar(con_corte, EMPRESA, CORTE,
                      gestion(compromiso_fecha=date(2026, 9, 15)))

    def test_un_compromiso_sin_fecha_se_rechaza(self, con_corte):
        with pytest.raises(ErrorDeGestion, match="Falta la fecha"):
            registrar(con_corte, EMPRESA, CORTE,
                      gestion(compromiso_valor=Decimal("500000")))

    def test_un_valor_no_positivo_se_rechaza(self, con_corte):
        with pytest.raises(ErrorDeGestion, match="mayor que cero"):
            registrar(
                con_corte, EMPRESA, CORTE,
                gestion(compromiso_fecha=date(2026, 9, 15),
                        compromiso_valor=Decimal("0")),
            )


class TestElReprocesoNoBorraLaGestion:
    """El fallo mas facil de introducir aqui.

    El motor siempre emite ACTIVA porque no sabe de gestiones. Si el upsert
    volcara ese valor, cada corrida nocturna borraria el trabajo del dia.
    """

    def test_reprocesar_el_corte_conserva_el_estado(self, con_corte):
        registrar(con_corte, EMPRESA, CORTE, gestion())
        ejecutar_corte(con_corte, FuenteFalsa(CARTERA), EMPRESA, CORTE)

        alerta = next(
            a for a in RepositorioCartera(con_corte).alertas_del_corte(
                EMPRESA, CORTE, solo_activas=False
            )
            if a.factura == "F-4"
        )
        assert alerta.estado == EstadoAlerta.GESTIONADA.value

    def test_una_alerta_cerrada_por_pago_no_se_reabre_al_gestionar(self, con_corte):
        septiembre = CORTE + timedelta(days=30)
        quedan = [m for m in CARTERA if m.factura != "F-6"]
        ejecutar_corte(con_corte, FuenteFalsa(quedan), EMPRESA, septiembre)

        cerrada = next(
            a for a in RepositorioCartera(con_corte).alertas_del_corte(
                EMPRESA, CORTE, solo_activas=False
            )
            if a.factura == "F-6"
        )
        assert cerrada.estado == EstadoAlerta.CERRADA_POR_PAGO.value

        registrar(con_corte, EMPRESA, CORTE, gestion(factura="F-6"))
        assert cerrada.estado == EstadoAlerta.CERRADA_POR_PAGO.value


class TestActivacionDeA12:
    """C-07: A12 solo puede evaluarse cuando existe historial de gestion."""

    def _con_umbral(self, sesion, dias=30):
        config_bd.fijar_parametro(
            sesion, EMPRESA, "A12", "dias_sin_gestion", dias, "admin"
        )

    def test_sin_umbral_sigue_inactiva(self, con_corte):
        corrida = ejecutar_corte(con_corte, FuenteFalsa(CARTERA), EMPRESA, CORTE)
        assert "A12" in corrida.resultado.reglas_inactivas

    def test_una_alerta_nueva_no_dispara_a12(self, con_corte):
        """El fallo que advertia C-07: sin referencia, se disparaba siempre."""
        self._con_umbral(con_corte)
        corrida = ejecutar_corte(con_corte, FuenteFalsa(CARTERA), EMPRESA, CORTE)
        assert "A12" not in corrida.resultado.reglas_inactivas
        assert not any(a.codigo == "A12" for a in corrida.resultado.alertas)

    def test_dispara_cuando_pasa_el_umbral_sin_gestion(self, con_corte):
        self._con_umbral(con_corte, dias=30)
        # 40 dias despues, sin haber gestionado nada.
        despues = CORTE + timedelta(days=40)
        corrida = ejecutar_corte(con_corte, FuenteFalsa(CARTERA), EMPRESA, despues)

        a12 = [a for a in corrida.resultado.alertas if a.codigo == "A12"]
        assert a12
        assert "40 dias sin gestion" in str(a12[0].explicacion)

    def test_gestionar_reinicia_la_cuenta(self, con_corte):
        self._con_umbral(con_corte, dias=30)
        # Se gestiona F-4 a los 20 dias; a los 40 aun no cumple 30 sin gestion.
        registrar(
            con_corte, EMPRESA, CORTE,
            gestion(momento=datetime(2026, 9, 10, 9, 0)),
        )
        despues = CORTE + timedelta(days=40)
        corrida = ejecutar_corte(con_corte, FuenteFalsa(CARTERA), EMPRESA, despues)

        facturas_con_a12 = {a.entidad for a in corrida.resultado.alertas if a.codigo == "A12"}
        assert "F-4" not in facturas_con_a12
        assert "F-5" in facturas_con_a12

    def test_el_historial_se_arma_en_consultas_agregadas(self, con_corte):
        registrar(con_corte, EMPRESA, CORTE, gestion())
        historial = construir_historial(con_corte, EMPRESA)
        assert historial.fue_gestionada(("900", "F-4"))
        assert historial.dias_sin_gestion(("900", "F-4"), CORTE) == 0
