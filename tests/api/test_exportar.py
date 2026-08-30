"""Salidas formales (§9) y el criterio de aceptacion de §13.

"El PDF y Excel muestran exactamente la misma clasificacion que la pantalla
para el mismo corte." No basta con que las tres se generen: tienen que
coincidir, y eso solo se garantiza si leen del mismo resultado persistido.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import pytest

from .conftest import CORTE, entrar

openpyxl = pytest.importorskip("openpyxl")


@pytest.fixture
def excel(cliente_corrido, CABECERA):
    r = cliente_corrido.get("/api/v1/exportar/excel", headers=CABECERA)
    assert r.status_code == 200, r.text
    return openpyxl.load_workbook(BytesIO(r.content))


class TestExcel:
    def test_se_descarga_con_nombre_y_tipo(self, cliente_corrido, CABECERA):
        r = cliente_corrido.get("/api/v1/exportar/excel", headers=CABECERA)
        assert "spreadsheetml" in r.headers["content-type"]
        assert f"cartera_E01_{CORTE:%Y%m%d}.xlsx" in r.headers["content-disposition"]

    def test_trae_las_cuatro_hojas(self, excel):
        assert excel.sheetnames == [
            "Alertas", "Riesgo por cliente", "Aging", "Parametros"
        ]

    def test_conserva_las_columnas_de_auditoria_de_9(self, excel):
        """§9: hay que poder auditar por que el sistema clasifico cada factura."""
        cabecera = [c.value for c in excel["Alertas"][1]]
        for columna in (
            "Codigo Alerta", "Etiqueta Alerta", "Prioridad", "Accion Sugerida",
            "Estado Alerta", "Dias Vencimiento", "Origen Dias", "Explicacion",
            "Saldo Bruto", "Valor Credito Aplicado",
        ):
            assert columna in cabecera, columna

    def test_cada_alerta_explica_por_que_esta(self, excel):
        hoja = excel["Alertas"]
        i = [c.value for c in hoja[1]].index("Explicacion")
        explicaciones = [f[i].value for f in hoja.iter_rows(min_row=2)]
        assert explicaciones and all(e for e in explicaciones)

    def test_la_hoja_de_aging_declara_la_identidad_de_c14(self, excel):
        etiquetas = [f[1].value for f in excel["Aging"].iter_rows(min_row=2)]
        assert "= Por vencer" in etiquetas
        assert "+ Vence hoy" in etiquetas
        assert "+ Vencida" in etiquetas

    def test_registra_con_que_parametros_se_calculo(self, excel):
        """Sin esto, dos exportaciones del mismo corte con umbrales distintos
        serian indistinguibles."""
        campos = {f[0].value: f[1].value for f in excel["Parametros"].iter_rows(min_row=2)}
        assert campos["Empresa"] == "E01"
        assert len(str(campos["Version de parametros"])) == 32


class TestPDF:
    def test_se_genera_un_pdf_valido(self, cliente_corrido, CABECERA):
        r = cliente_corrido.get("/api/v1/exportar/pdf", headers=CABECERA)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF-")

    def test_lleva_la_fecha_de_corte_en_el_nombre(self, cliente_corrido, CABECERA):
        r = cliente_corrido.get("/api/v1/exportar/pdf", headers=CABECERA)
        assert f"cartera_E01_{CORTE:%Y%m%d}.pdf" in r.headers["content-disposition"]


class TestCoincidenciaEntreSalidas:
    """§13, criterio de aceptacion. Es el entregable de la etapa 7."""

    def test_el_total_de_cartera_coincide_en_pantalla_y_excel(
        self, cliente_corrido, CABECERA, excel
    ):
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        de_pantalla = Decimal(
            next(k["valor"] for k in panel["kpis"] if k["codigo"] == "cartera_total")
        )

        aging = excel["Aging"]
        etiquetas = [f[1].value for f in aging.iter_rows(min_row=2)]
        fila = etiquetas.index("Cartera total") + 2
        assert Decimal(str(aging.cell(row=fila, column=5).value)) == de_pantalla

    def test_el_numero_de_alertas_coincide(self, cliente_corrido, CABECERA, excel):
        lista = cliente_corrido.get(
            "/api/v1/gestion", params={"estado": None, "por_pagina": 500},
            headers=CABECERA,
        ).json()
        assert excel["Alertas"].max_row - 1 == lista["total"]

    def test_el_aging_coincide_bucket_a_bucket(
        self, cliente_corrido, CABECERA, excel
    ):
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        de_pantalla = {b["bucket"]: Decimal(b["saldo"]) for b in panel["aging"]}

        for fila in excel["Aging"].iter_rows(min_row=2):
            codigo = fila[0].value
            if codigo in de_pantalla:
                assert Decimal(str(fila[4].value)) == de_pantalla[codigo], codigo

    def test_la_prioridad_de_cada_cliente_coincide(
        self, cliente_corrido, CABECERA, excel
    ):
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        de_pantalla = {c["cliente_nit"]: c["prioridad_etiqueta"] for c in panel["ranking"]}

        hoja = excel["Riesgo por cliente"]
        for fila in hoja.iter_rows(min_row=2):
            nit = str(fila[0].value)
            if nit in de_pantalla:
                assert fila[13].value == de_pantalla[nit], nit


class TestPermisos:
    def test_consulta_puede_exportar(self, cliente_corrido):
        """Exportar es leer: no exige un rol mas alto."""
        r = cliente_corrido.get(
            "/api/v1/exportar/excel", headers=entrar(cliente_corrido, "ana")
        )
        assert r.status_code == 200

    def test_sin_token_no_se_exporta(self, cliente_corrido):
        assert cliente_corrido.get("/api/v1/exportar/excel").status_code == 401


class TestContenidoDelPDF:
    """El PDF comprime su texto: comprobar bytes crudos no demuestra nada.

    Estas pruebas lo extraen de verdad, que es la unica forma de saber que el
    reporte formal dice lo mismo que la pantalla (§13).
    """

    @pytest.fixture
    def texto(self, cliente_corrido, CABECERA):
        pypdf = pytest.importorskip("pypdf")
        from io import BytesIO

        r = cliente_corrido.get("/api/v1/exportar/pdf", headers=CABECERA)
        lector = pypdf.PdfReader(BytesIO(r.content))
        return "\n".join(p.extract_text() for p in lector.pages)

    def test_lleva_la_fecha_de_corte(self, texto):
        assert f"{CORTE:%d/%m/%Y}" in texto

    def test_lleva_los_indicadores_de_81(self, texto):
        for etiqueta in ("CARTERA TOTAL", "POR VENCER", "VENCE HOY", "VENCIDA"):
            assert etiqueta in texto, etiqueta

    def test_lleva_la_version_de_parametros(self, texto):
        """Sin ella, dos PDF del mismo corte con umbrales distintos serian
        indistinguibles ante una auditoria."""
        assert "parametros" in texto

    def test_el_total_coincide_con_la_pantalla(
        self, texto, cliente_corrido, CABECERA
    ):
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        total = next(k for k in panel["kpis"] if k["codigo"] == "cartera_total")
        # El PDF formatea con puntos de millar, como la pantalla.
        esperado = f"{int(float(total['valor'])):,}".replace(",", ".")
        assert esperado in texto

    def test_cada_alerta_explica_por_que_esta(self, texto):
        """§7.4 tambien en el reporte formal: no basta con el codigo de alerta,
        hay que poder defender ante una junta por que se disparo."""
        assert "la factura esta en el rango" in texto
