"""Reconciliacion contra el archivo de prueba de BUSINT.

§8 pide, como entregable verificable de la etapa 1, "la reconciliacion contra el
archivo de prueba". Estas pruebas comparan lo que calcula el motor contra lo que
el propio ERP ya trae calculado en sus columnas de aging.

El archivo es sintetico (30 NIT y 120 facturas generados), asi que no contiene
datos de clientes reales.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from busint_alertas.core.motor import ContextoEjecucion
from busint_alertas.motores.cartera import ConfiguracionCartera, MotorCartera
from busint_alertas.motores.cartera.configuracion import COLUMNAS_ERP

openpyxl = pytest.importorskip("openpyxl")

from busint_alertas.fuentes import FuenteExcel  # noqa: E402

ARCHIVO = Path(__file__).parent.parent / "datos" / "cartera_busint_sintetica.xlsx"
CORTE = date(2026, 8, 21)
EMPRESA = "E01"

#: Columnas de aging del archivo, tal como las nombra el ERP.
COL_ERP = {
    "Valor por Vencer": "Valor por Vencer",
    "<=30": "Valor vencido menor o igual a 30 días",
    "<=60": "Valor vencido menor o igual a 60 días",
    "<=90": "Valor vencido menor o igual a 90 días",
    "<=120": "Valor vencido menor o igual a 120 días",
    "<=150": "Valor vencido menor o igual a 150 días",
    ">150": "Varlo vencido a mas de 150",
}


@pytest.fixture(scope="module")
def filas_erp() -> list[dict]:
    libro = openpyxl.load_workbook(ARCHIVO, data_only=True)
    hoja = libro[libro.sheetnames[0]]
    todo = list(hoja.iter_rows(values_only=True))
    libro.close()
    return [dict(zip(todo[0], f)) for f in todo[1:]]


@pytest.fixture(scope="module")
def movimientos() -> list:
    return list(FuenteExcel(ARCHIVO).leer(EMPRESA, CORTE))


@pytest.fixture(scope="module")
def resultado(movimientos):
    config = ConfiguracionCartera.plantilla(
        EMPRESA,
        dias_preventivos=5,
        n_facturas_vencidas=3,
        pct_mayor_90_umbral=Decimal("40"),
    )
    contexto = ContextoEjecucion(empresa_id=EMPRESA, corte=CORTE, configuracion=config)
    return MotorCartera().evaluar(contexto, movimientos)


def dec(v) -> Decimal:
    return Decimal(str(v or 0))


class TestLectura:
    def test_se_leen_las_120_facturas(self, movimientos):
        assert len(movimientos) == 120

    def test_hay_30_clientes(self, movimientos):
        assert len({m.cliente_nit for m in movimientos}) == 30

    def test_leer_con_otro_corte_falla(self):
        """El archivo declara su corte; procesarlo contra otro es un error."""
        from busint_alertas.fuentes import ErrorDeOrigen

        with pytest.raises(ErrorDeOrigen, match="corresponde al corte"):
            list(FuenteExcel(ARCHIVO).leer(EMPRESA, date(2026, 9, 30)))


class TestDiasVencimiento:
    """C-01 verificado contra las 120 filas, como afirma el documento."""

    def test_reproduce_la_columna_dias_vencimiento(self, movimientos, filas_erp):
        esperado = {str(f["Num Fact"]): f["Dias Vencimiento"] for f in filas_erp}
        for mov in movimientos:
            assert mov.dias_vencimiento(CORTE) == esperado[mov.factura], mov.factura

    def test_la_fecha_de_emision_habria_dado_otro_resultado(self, movimientos, filas_erp):
        """Confirma que la contradiccion de C-01 era real y no teorica.

        Si se contaran los dias contra la fecha de emision, ninguna factura del
        archivo daria el valor que el propio ERP reporta.
        """
        por_emision = {str(f["Num Fact"]): f["Dias Fact"] for f in filas_erp}
        distintos = sum(
            1 for m in movimientos if m.dias_vencimiento(CORTE) != por_emision[m.factura]
        )
        assert distintos == 120


class TestAging:
    def test_el_total_de_cartera_coincide(self, resultado, filas_erp):
        assert resultado.indicadores["globales"]["cartera_total"] == sum(
            dec(f["Valor Total"]) for f in filas_erp
        )

    @pytest.mark.parametrize(
        "columna, buckets",
        [
            ("Valor por Vencer", ("B00",)),
            ("<=30", ("B01", "B02")),
            ("<=60", ("B03",)),
            ("<=90", ("B04",)),
            ("<=120", ("B05",)),
            ("<=150", ("B06",)),
            (">150", ("B07",)),
        ],
    )
    def test_cada_columna_del_erp_se_reproduce(
        self, resultado, filas_erp, columna, buckets
    ):
        """El motor reproduce las columnas de aging que el ERP ya calcula.

        La columna "<=30" del ERP corresponde a dos buckets del motor porque el
        ERP no separa "vence hoy" y el motor si (C-14).
        """
        del_erp = sum(dec(f[COL_ERP[columna]]) for f in filas_erp)
        por_bucket = resultado.indicadores["globales"]["por_bucket"]
        del_motor = sum(por_bucket.get(b, Decimal("0")) for b in buckets)
        assert del_motor == del_erp

    def test_el_mapeo_de_columnas_documentado_es_el_que_se_usa(self):
        """COLUMNAS_ERP debe seguir describiendo la equivalencia real."""
        assert COLUMNAS_ERP["Valor vencido menor o igual a 30 dias"] == ("B01", "B02")


class TestVenceHoy:
    """C-14 medido sobre datos reales, no como argumento teorico."""

    def test_el_erp_cuenta_vence_hoy_como_vencida(self, resultado, filas_erp):
        vence_hoy = resultado.indicadores["globales"]["vence_hoy"]
        del_erp_30 = sum(dec(f[COL_ERP["<=30"]]) for f in filas_erp)
        b02 = resultado.indicadores["globales"]["por_bucket"]["B02"]

        assert vence_hoy == Decimal("84500000.00")
        assert del_erp_30 == vence_hoy + b02

    def test_la_identidad_de_cartera_se_cumple(self, resultado):
        g = resultado.indicadores["globales"]
        assert g["por_vencer"] + g["vence_hoy"] + g["vencida"] == g["cartera_total"]


class TestValorCredito:
    """C-10 sigue abierta: el archivo no aporta evidencia en ningun sentido."""

    def test_el_archivo_no_ejerce_las_notas_credito(self, filas_erp):
        assert all(dec(f["Valor Credito"]) == 0 for f in filas_erp)

    def test_valor_total_igual_a_valor_original_en_todo_el_archivo(self, filas_erp):
        assert all(dec(f["Valor Total"]) == dec(f["Valor Original"]) for f in filas_erp)
