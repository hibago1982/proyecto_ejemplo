"""Origenes de datos: mapeo, normalizacion, archivo plano y API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from busint_alertas.fuentes import (
    ErrorDeOrigen,
    FuenteAPI,
    FuenteCSV,
    FuenteDatos,
    MapeoCampos,
    construir_movimiento,
)
from busint_alertas.fuentes.api import _sin_credenciales

MAPEO = MapeoCampos(
    cliente_nit="nit",
    factura="fact",
    fecha_emision="emision",
    fecha_vencimiento="vence",
    saldo="saldo",
    empresa_id_fijo="E01",
)


def registro(**cambios):
    base = {
        "nit": "900123",
        "fact": "F-1",
        "emision": "2026-07-01",
        "vence": "2026-07-31",
        "saldo": "1000000",
    }
    base.update(cambios)
    return base


class TestNormalizacion:
    @pytest.mark.parametrize(
        "valor",
        ["2026-07-31", "31/07/2026", "2026/07/31", "31-07-2026", "2026-07-31T00:00:00"],
    )
    def test_acepta_los_formatos_de_fecha_habituales(self, valor):
        mov = construir_movimiento(registro(vence=valor), MAPEO)
        assert mov.fecha_vencimiento == date(2026, 7, 31)

    @pytest.mark.parametrize(
        "valor, esperado",
        [
            ("1234567.89", "1234567.89"),
            ("1.234.567,89", "1234567.89"),
            ("1234567,89", "1234567.89"),
            ("$ 1.234.567,89", "1234567.89"),
            (1234567.89, "1234567.89"),
            (1234567, "1234567.00"),
            ("", "0.00"),
            (None, "0.00"),
        ],
    )
    def test_interpreta_montos_en_formato_colombiano(self, valor, esperado):
        mov = construir_movimiento(registro(saldo=valor), MAPEO)
        assert mov.saldo == Decimal(esperado)

    def test_una_fecha_ilegible_dice_que_factura_la_trae(self):
        with pytest.raises(ErrorDeOrigen, match="F-1.*'vence'"):
            construir_movimiento(registro(vence="ayer"), MAPEO)

    def test_un_monto_ilegible_dice_que_factura_lo_trae(self):
        with pytest.raises(ErrorDeOrigen, match="F-1.*'saldo'"):
            construir_movimiento(registro(saldo="mucho"), MAPEO)

    def test_una_columna_ausente_se_reporta_con_su_nombre(self):
        incompleto = registro()
        del incompleto["vence"]
        with pytest.raises(ErrorDeOrigen, match=r"no trae las columnas \['vence'\]"):
            construir_movimiento(incompleto, MAPEO)


class TestEmpresa:
    """C-08: sin empresa no se procesa nada."""

    def test_sin_columna_ni_constante_se_rechaza(self):
        sin_empresa = MapeoCampos(
            cliente_nit="nit", factura="fact", fecha_emision="emision",
            fecha_vencimiento="vence", saldo="saldo",
        )
        with pytest.raises(ErrorDeOrigen, match="aislamiento por empresa"):
            construir_movimiento(registro(), sin_empresa)

    def test_la_columna_tiene_prioridad_sobre_la_constante(self):
        from dataclasses import replace

        mapeo = replace(MAPEO, empresa_id="empresa")
        mov = construir_movimiento(registro(empresa="E99"), mapeo)
        assert mov.empresa_id == "E99"

    def test_si_la_columna_viene_vacia_se_usa_la_constante(self):
        from dataclasses import replace

        mapeo = replace(MAPEO, empresa_id="empresa")
        mov = construir_movimiento(registro(empresa=None), mapeo)
        assert mov.empresa_id == "E01"


class TestFuenteCSV:
    def test_lee_un_csv(self, tmp_path):
        archivo = tmp_path / "cartera.csv"
        archivo.write_text(
            "nit,fact,emision,vence,saldo\n"
            "900123,F-1,2026-07-01,2026-07-31,1000000\n"
            "900124,F-2,2026-07-05,2026-08-04,2000000\n",
            encoding="utf-8",
        )
        movs = list(FuenteCSV(archivo, MAPEO).leer("E01", date(2026, 8, 21)))
        assert [m.factura for m in movs] == ["F-1", "F-2"]

    def test_un_archivo_inexistente_lo_dice(self, tmp_path):
        with pytest.raises(ErrorDeOrigen, match="No existe el archivo"):
            list(FuenteCSV(tmp_path / "no_esta.csv", MAPEO).leer("E01", date(2026, 8, 21)))


class TransporteFalso:
    """Devuelve respuestas preparadas y registra las URL pedidas."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.pedidas: list[str] = []
        self.cabeceras: list[dict] = []

    def obtener(self, url, cabeceras):
        self.pedidas.append(url)
        self.cabeceras.append(dict(cabeceras))
        return self.respuestas.pop(0)


class TestFuenteAPI:
    def test_cumple_el_contrato_de_fuente(self):
        assert isinstance(FuenteAPI("https://erp", MAPEO), FuenteDatos)

    def test_lee_una_pagina(self):
        transporte = TransporteFalso([{"datos": [registro(), registro(fact="F-2")]}])
        fuente = FuenteAPI("https://erp/api", MAPEO, transporte=transporte)
        movs = list(fuente.leer("E01", date(2026, 8, 21)))
        assert [m.factura for m in movs] == ["F-1", "F-2"]

    def test_pide_empresa_y_corte_como_parametros(self):
        transporte = TransporteFalso([{"datos": []}])
        list(FuenteAPI("https://erp/api", MAPEO, transporte=transporte).leer("E07", date(2026, 8, 21)))
        assert "empresa=E07" in transporte.pedidas[0]
        assert "corte=2026-08-21" in transporte.pedidas[0]

    def test_recorre_la_paginacion(self):
        transporte = TransporteFalso([
            {"datos": [registro(fact="F-1")], "siguiente": "https://erp/api?p=2"},
            {"datos": [registro(fact="F-2")], "siguiente": "https://erp/api?p=3"},
            {"datos": [registro(fact="F-3")], "siguiente": None},
        ])
        fuente = FuenteAPI("https://erp/api", MAPEO, transporte=transporte)
        assert len(list(fuente.leer("E01", date(2026, 8, 21)))) == 3
        assert len(transporte.pedidas) == 3

    def test_una_pagina_repetida_no_cuelga_el_proceso(self):
        repetida = "https://erp/api?p=1"
        transporte = TransporteFalso([
            {"datos": [registro()], "siguiente": repetida},
            {"datos": [registro()], "siguiente": repetida},
        ])
        fuente = FuenteAPI("https://erp/api", MAPEO, transporte=transporte)
        with pytest.raises(ErrorDeOrigen, match="pagina repetida"):
            list(fuente.leer("E01", date(2026, 8, 21)))

    def test_acepta_una_lista_al_desnudo(self):
        transporte = TransporteFalso([[registro()]])
        fuente = FuenteAPI("https://erp/api", MAPEO, transporte=transporte)
        assert len(list(fuente.leer("E01", date(2026, 8, 21)))) == 1

    def test_si_falta_la_lista_dice_que_claves_llegaron(self):
        transporte = TransporteFalso([{"resultados": []}])
        fuente = FuenteAPI("https://erp/api", MAPEO, transporte=transporte)
        with pytest.raises(ErrorDeOrigen, match=r"Claves recibidas: \['resultados'\]"):
            list(fuente.leer("E01", date(2026, 8, 21)))

    def test_envia_el_token_como_bearer(self):
        transporte = TransporteFalso([{"datos": []}])
        fuente = FuenteAPI("https://erp/api", MAPEO, token="secreto", transporte=transporte)
        list(fuente.leer("E01", date(2026, 8, 21)))
        assert transporte.cabeceras[0]["Authorization"] == "Bearer secreto"

    def test_filtra_por_empresa_aunque_el_api_devuelva_de_mas(self):
        from dataclasses import replace

        mapeo = replace(MAPEO, empresa_id="empresa", empresa_id_fijo=None)
        transporte = TransporteFalso([{"datos": [
            registro(fact="F-1", empresa="E01"),
            registro(fact="F-2", empresa="E02"),
        ]}])
        fuente = FuenteAPI("https://erp/api", mapeo, transporte=transporte)
        movs = list(fuente.leer("E01", date(2026, 8, 21)))
        assert [m.factura for m in movs] == ["F-1"]


class TestCredencialesEnLosMensajes:
    """Un error termina en los logs; no puede llevar credenciales dentro."""

    def test_se_oculta_la_contrasena_de_la_url(self):
        limpia = _sin_credenciales("https://user:clave@erp.co/api?empresa=E01")
        assert "clave" not in limpia and "user" not in limpia
        assert "erp.co" in limpia

    @pytest.mark.parametrize("param", ["token", "apikey", "api_key", "access_token"])
    def test_se_ocultan_los_tokens_del_query(self, param):
        limpia = _sin_credenciales(f"https://erp.co/api?{param}=abc123&empresa=E01")
        assert "abc123" not in limpia
        assert "empresa=E01" in limpia
