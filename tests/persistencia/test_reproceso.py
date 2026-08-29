"""Entregable verificable de la etapa 2 (§8).

"Reproceso del mismo corte sin duplicados y regeneracion identica de un corte
pasado." Son los dos riesgos tecnicos C-17 y C-16.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from busint_alertas.ejecucion import ejecutar_corte
from busint_alertas.motores.cartera import Movimiento
from busint_alertas.persistencia import RepositorioCartera, version_de
from busint_alertas.persistencia import configuracion as config_bd
from busint_alertas.persistencia.modelo import SIN_FACTURA

from .conftest import EMPRESA

CORTE = date(2026, 8, 21)


def factura(numero, dias, saldo="1000000", nit="900"):
    venc = CORTE - timedelta(days=dias)
    return Movimiento(
        empresa_id=EMPRESA, cliente_nit=nit, factura=numero,
        fecha_emision=venc - timedelta(days=30), fecha_vencimiento=venc,
        saldo=Decimal(saldo), cliente_nombre="Cliente Demo",
    )


class FuenteFalsa:
    """Origen en memoria. El motor no distingue de donde vienen los datos."""

    def __init__(self, movimientos):
        self.movimientos = list(movimientos)

    def leer(self, empresa_id, corte):
        return iter(self.movimientos)


CARTERA = [
    factura("F-1", -10), factura("F-2", 0), factura("F-3", 15),
    factura("F-4", 45), factura("F-5", 100), factura("F-6", 200),
]


class TestReprocesoSinDuplicados:
    """C-17: la clave logica, materializada como restriccion unica."""

    def test_reprocesar_no_duplica(self, sesion_sembrada):
        fuente = FuenteFalsa(CARTERA)
        primera = ejecutar_corte(sesion_sembrada, fuente, EMPRESA, CORTE)
        segunda = ejecutar_corte(sesion_sembrada, fuente, EMPRESA, CORTE)

        assert primera.resumen.alertas_insertadas > 0
        assert segunda.resumen.alertas_insertadas == 0
        assert segunda.resumen.alertas_actualizadas == primera.resumen.alertas_insertadas

    def test_el_numero_de_filas_no_crece(self, sesion_sembrada):
        fuente = FuenteFalsa(CARTERA)
        repo = RepositorioCartera(sesion_sembrada)
        for _ in range(3):
            ejecutar_corte(sesion_sembrada, fuente, EMPRESA, CORTE)
        assert len(repo.alertas_del_corte(EMPRESA, CORTE)) == len(
            ejecutar_corte(sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE).resultado.alertas
        )

    def test_la_restriccion_unica_existe_en_la_tabla(self, sesion_sembrada):
        from busint_alertas.persistencia.modelo import Alerta

        nombres = {c.name for c in Alerta.__table__.constraints}
        assert "uq_alerta_clave_logica" in nombres

    def test_una_alerta_de_cliente_usa_cadena_vacia_y_no_nulo(self, sesion_sembrada):
        """Dos NULL no son iguales en SQL: con NULL la restriccion no aplicaria."""
        ejecutar_corte(sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE)
        repo = RepositorioCartera(sesion_sembrada)
        de_cliente = [
            a for a in repo.alertas_del_corte(EMPRESA, CORTE) if a.codigo == "A10"
        ]
        assert de_cliente
        assert all(a.factura == SIN_FACTURA for a in de_cliente)

    def test_el_resultado_del_reproceso_es_identico(self, sesion_sembrada):
        fuente = FuenteFalsa(CARTERA)
        repo = RepositorioCartera(sesion_sembrada)

        ejecutar_corte(sesion_sembrada, fuente, EMPRESA, CORTE)
        antes = [(a.codigo, a.cliente_nit, a.factura, a.prioridad, a.saldo)
                 for a in repo.alertas_del_corte(EMPRESA, CORTE)]

        ejecutar_corte(sesion_sembrada, fuente, EMPRESA, CORTE)
        despues = [(a.codigo, a.cliente_nit, a.factura, a.prioridad, a.saldo)
                   for a in repo.alertas_del_corte(EMPRESA, CORTE)]

        assert antes == despues


class TestSnapshot:
    """C-16: sin congelar el corte, un corte pasado es irrecuperable."""

    def test_cada_corrida_congela_el_corte(self, sesion_sembrada):
        ejecutar_corte(sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE)
        snapshot = RepositorioCartera(sesion_sembrada).snapshot_del_corte(EMPRESA, CORTE)
        assert len(snapshot) == 1
        assert snapshot[0].cartera_total == Decimal("6000000.00")

    def test_el_snapshot_guarda_los_totales_por_bucket(self, sesion_sembrada):
        ejecutar_corte(sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE)
        fila = RepositorioCartera(sesion_sembrada).snapshot_del_corte(EMPRESA, CORTE)[0]
        assert fila.totales_por_bucket["B00"] == "1000000.00"
        assert fila.totales_por_bucket["B01"] == "1000000.00"
        assert fila.totales_por_bucket["B07"] == "1000000.00"

    def test_un_corte_pasado_se_lee_del_snapshot_no_del_erp(self, sesion_sembrada):
        """El escenario que hace obligatorio el snapshot.

        Se corre agosto; en septiembre el cliente pago tres facturas y el ERP
        ya no las expone. El corte de agosto debe seguir mostrando lo que habia
        en agosto.
        """
        repo = RepositorioCartera(sesion_sembrada)
        ejecutar_corte(sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE)
        agosto = repo.snapshot_del_corte(EMPRESA, CORTE)[0]
        total_agosto = agosto.cartera_total

        septiembre = CORTE + timedelta(days=30)
        quedan = [m for m in CARTERA if m.factura in {"F-5", "F-6"}]
        ejecutar_corte(sesion_sembrada, FuenteFalsa(quedan), EMPRESA, septiembre)

        # El snapshot de agosto no se movio, aunque el ERP ya no tenga esas facturas.
        assert repo.snapshot_del_corte(EMPRESA, CORTE)[0].cartera_total == total_agosto
        assert repo.snapshot_del_corte(EMPRESA, septiembre)[0].cartera_total == Decimal("2000000.00")

    def test_se_guarda_la_version_de_parametros(self, sesion_sembrada):
        """Sin ella, dos cortes con umbrales distintos serian indistinguibles."""
        corrida = ejecutar_corte(sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE)
        fila = RepositorioCartera(sesion_sembrada).snapshot_del_corte(EMPRESA, CORTE)[0]
        assert fila.version_parametros == corrida.resumen.version_parametros
        assert len(fila.version_parametros) == 32

    def test_cambiar_un_umbral_cambia_la_version(self, sesion_sembrada):
        antes = version_de(config_bd.cargar(sesion_sembrada, EMPRESA))
        config_bd.fijar_parametro(
            sesion_sembrada, EMPRESA, "R03", "n_facturas_vencidas", 5, "admin"
        )
        despues = version_de(config_bd.cargar(sesion_sembrada, EMPRESA))
        assert antes != despues

    def test_los_cortes_disponibles_se_listan_del_mas_reciente(self, sesion_sembrada):
        repo = RepositorioCartera(sesion_sembrada)
        for dias in (0, 30, 60):
            ejecutar_corte(
                sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE + timedelta(days=dias)
            )
        assert repo.cortes_disponibles(EMPRESA) == [
            CORTE + timedelta(days=60), CORTE + timedelta(days=30), CORTE
        ]


class TestCierrePorAusencia:
    """C-18: el ERP no emite evento de pago; la factura simplemente desaparece."""

    def test_la_factura_que_desaparece_cierra_su_alerta(self, sesion_sembrada):
        repo = RepositorioCartera(sesion_sembrada)
        ejecutar_corte(sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE)

        septiembre = CORTE + timedelta(days=30)
        quedan = [m for m in CARTERA if m.factura != "F-6"]
        corrida = ejecutar_corte(sesion_sembrada, FuenteFalsa(quedan), EMPRESA, septiembre)

        assert corrida.resumen.alertas_cerradas >= 1
        cerradas = [
            a for a in repo.alertas_del_corte(EMPRESA, CORTE, solo_activas=False)
            if a.estado == "cerrada_por_pago"
        ]
        assert {a.factura for a in cerradas} == {"F-6"}
        assert all(a.detectado_pago == septiembre for a in cerradas)

    def test_la_primera_corrida_no_cierra_nada(self, sesion_sembrada):
        corrida = ejecutar_corte(sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE)
        assert corrida.resumen.alertas_cerradas == 0

    def test_las_facturas_que_siguen_abiertas_no_se_cierran(self, sesion_sembrada):
        repo = RepositorioCartera(sesion_sembrada)
        ejecutar_corte(sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE)
        ejecutar_corte(
            sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE + timedelta(days=30)
        )
        activas = repo.alertas_del_corte(EMPRESA, CORTE)
        assert activas


class TestBitacora:
    """§10.2: registrar fecha y hora de la ultima evaluacion."""

    def test_cada_corrida_deja_registro(self, sesion_sembrada):
        from sqlalchemy import select
        from busint_alertas.persistencia.modelo import Ejecucion

        ejecutar_corte(sesion_sembrada, FuenteFalsa(CARTERA), EMPRESA, CORTE)
        fila = sesion_sembrada.scalars(select(Ejecucion)).one()
        assert fila.estado == "ok"
        assert fila.filas_procesadas == 6
        assert fila.alertas_generadas > 0
        assert fila.fin is not None

    def test_un_fallo_queda_registrado_como_error(self, sesion_sembrada):
        from sqlalchemy import select
        from busint_alertas.persistencia.modelo import Ejecucion

        class FuenteQueFalla:
            def leer(self, empresa_id, corte):
                raise RuntimeError("el ERP no responde")

        with pytest.raises(RuntimeError, match="el ERP no responde"):
            ejecutar_corte(sesion_sembrada, FuenteQueFalla(), EMPRESA, CORTE)

        fila = sesion_sembrada.scalars(select(Ejecucion)).one()
        assert fila.estado == "error"
        assert "el ERP no responde" in fila.mensaje
