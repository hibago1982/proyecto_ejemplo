"""C-01 (dias contra fecha de vencimiento) y clasificacion en buckets."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from busint_alertas.motores.cartera import Movimiento
from busint_alertas.motores.cartera.buckets import Bucket, ConfiguracionBuckets
from busint_alertas.motores.cartera.configuracion import BUCKETS_PLANTILLA
from busint_alertas.core.tipos import Prioridad

from ..conftest import CORTE, factura


class TestDiasVencimiento:
    def test_se_calculan_contra_el_vencimiento_y_no_contra_la_emision(self):
        """C-01: §5.1 decia fecha inicial y §10.1 fecha de vencimiento.

        Se adopta el vencimiento. Con emision y vencimiento separados 30 dias,
        la diferencia entre ambos criterios es justamente de 30.
        """
        mov = Movimiento(
            empresa_id="E01",
            cliente_nit="900",
            factura="F-1",
            fecha_emision=date(2026, 7, 1),
            fecha_vencimiento=date(2026, 7, 31),
            saldo=Decimal("100"),
        )
        assert mov.dias_vencimiento(date(2026, 8, 31)) == 31

    def test_vence_hoy_son_cero_dias(self):
        assert factura(dias_vencida=0).dias_vencimiento(CORTE) == 0

    def test_por_vencer_da_negativo(self):
        assert factura(dias_vencida=-10).dias_vencimiento(CORTE) == -10

    def test_vencimiento_anterior_a_emision_se_rechaza(self):
        with pytest.raises(ValueError, match="anterior a la de emision"):
            Movimiento(
                empresa_id="E01",
                cliente_nit="900",
                factura="F-1",
                fecha_emision=date(2026, 8, 1),
                fecha_vencimiento=date(2026, 7, 1),
                saldo=Decimal("100"),
            )


class TestAsignacionDeBuckets:
    @pytest.mark.parametrize(
        "dias, esperado",
        [
            (-60, "B00"),
            (-1, "B00"),
            (0, "B01"),
            (1, "B02"),
            (30, "B02"),
            (31, "B03"),
            (90, "B04"),
            (91, "B05"),
            (150, "B05"),
            (151, "B06"),
            (900, "B06"),
        ],
    )
    def test_los_limites_caen_donde_deben(self, dias, esperado):
        buckets = ConfiguracionBuckets(BUCKETS_PLANTILLA)
        assert buckets.asignar(dias).codigo == esperado

    def test_vence_hoy_no_es_ni_por_vencer_ni_vencida(self):
        """C-14: el bucket B01 es una categoria propia, no un caso de las otras."""
        b01 = ConfiguracionBuckets(BUCKETS_PLANTILLA).obtener("B01")
        assert b01.es_vence_hoy
        assert not b01.es_por_vencer
        assert not b01.es_vencida


class TestValidacionDeConfiguracion:
    """Un hueco o un solapamiento entre buckets se detecta al configurar.

    Si no, se manifiesta en produccion como indicadores que no cuadran, que es
    mucho mas dificil de diagnosticar.
    """

    def _bucket(self, codigo, desde, hasta, orden):
        return Bucket(codigo, codigo, desde, hasta, "#000", Prioridad.MEDIA, "-", orden)

    def test_hueco_entre_buckets(self):
        with pytest.raises(ValueError, match="hueco o se solapan"):
            ConfiguracionBuckets([
                self._bucket("A", None, 10, 0),
                self._bucket("B", 20, None, 1),
            ])

    def test_solapamiento_entre_buckets(self):
        with pytest.raises(ValueError, match="hueco o se solapan"):
            ConfiguracionBuckets([
                self._bucket("A", None, 30, 0),
                self._bucket("B", 20, None, 1),
            ])

    def test_el_ultimo_bucket_debe_quedar_abierto(self):
        with pytest.raises(ValueError, match="debe cerrar sin limite superior"):
            ConfiguracionBuckets([
                self._bucket("A", None, 10, 0),
                self._bucket("B", 11, 100, 1),
            ])

    def test_se_exige_al_menos_un_bucket_activo(self):
        with pytest.raises(ValueError, match="al menos un bucket activo"):
            ConfiguracionBuckets([])
