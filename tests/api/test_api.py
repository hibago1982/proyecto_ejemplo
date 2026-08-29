"""API REST: contrato, panel, lista de gestion, detalle y configuracion."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .conftest import CABECERA, CARTERA, CORTE, EMPRESA


class TestContrato:
    def test_publica_el_openapi(self, cliente):
        contrato = cliente.get("/openapi.json").json()
        assert contrato["openapi"].startswith("3.")
        assert contrato["info"]["title"].startswith("BUSINT")

    def test_expone_los_endpoints_de_seccion_8(self, cliente):
        rutas = set(cliente.get("/openapi.json").json()["paths"])
        for ruta in (
            "/api/v1/panel",
            "/api/v1/gestion",
            "/api/v1/clientes/{cliente_nit}",
            "/api/v1/configuracion",
            "/api/v1/ejecucion",
            "/api/v1/cortes",
        ):
            assert ruta in rutas, ruta

    def test_los_montos_son_cadena_y_no_numero(self, cliente_corrido):
        """C-09: un float de JavaScript no representa 1234567.89 sin error."""
        contrato = cliente_corrido.get("/openapi.json").json()
        kpi = contrato["components"]["schemas"]["TarjetaKPI"]["properties"]
        assert kpi["valor"]["type"] == "string"

        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        assert isinstance(panel["kpis"][0]["valor"], str)

    def test_la_sonda_de_salud_responde(self, cliente):
        assert cliente.get("/salud").json() == {"estado": "ok"}


class TestEmpresaEnContexto:
    def test_sin_cabecera_se_rechaza(self, cliente_corrido):
        assert cliente_corrido.get("/api/v1/panel").status_code == 422

    def test_una_empresa_sin_cortes_da_404(self, cliente_corrido):
        r = cliente_corrido.get("/api/v1/panel", headers={"X-Empresa-Id": "E99"})
        assert r.status_code == 404
        assert "no tiene ningun corte" in r.json()["detail"]


class TestPanel:
    def test_los_kpis_cuadran_con_la_identidad_de_cartera(self, cliente_corrido):
        """C-14: total = por vencer + vence hoy + vencida."""
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        kpis = {k["codigo"]: Decimal(k["valor"]) for k in panel["kpis"]}
        assert (
            kpis["por_vencer"] + kpis["vence_hoy"] + kpis["vencida"]
            == kpis["cartera_total"]
        )

    def test_el_aging_incluye_el_bucket_por_vencer(self, cliente_corrido):
        """B00 no emite alerta: si el aging saliera de ar_alerta, faltaria."""
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        b00 = next(b for b in panel["aging"] if b["bucket"] == "B00")
        assert Decimal(b00["saldo"]) == Decimal("1000000.00")

    def test_el_aging_trae_los_ocho_buckets(self, cliente_corrido):
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        assert [b["bucket"] for b in panel["aging"]] == [f"B0{i}" for i in range(8)]

    def test_los_porcentajes_los_calcula_el_servidor(self, cliente_corrido):
        """§16: una sola fuente de calculo, tambien para los indicadores."""
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        total = next(k for k in panel["kpis"] if k["codigo"] == "cartera_total")
        assert total["pct_sobre_total"] == "100.00"

    def test_el_corte_por_defecto_es_el_ultimo_calculado(self, cliente_corrido):
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        assert panel["corte"] == str(CORTE)

    def test_se_listan_los_cortes_disponibles(self, cliente_corrido):
        cortes = cliente_corrido.get("/api/v1/cortes", headers=CABECERA).json()
        assert len(cortes) == 1
        assert cortes[0]["corte"] == str(CORTE)
        assert cortes[0]["n_clientes"] == 1


class TestListaGestion:
    def test_devuelve_las_alertas_del_corte(self, cliente_corrido):
        lista = cliente_corrido.get("/api/v1/gestion", headers=CABECERA).json()
        assert lista["total"] > 0
        assert lista["filas"]

    def test_cada_fila_explica_por_que_esta_ahi(self, cliente_corrido):
        """§7.4: sin explicacion, el semaforo no es defendible."""
        lista = cliente_corrido.get("/api/v1/gestion", headers=CABECERA).json()
        assert all(f["explicacion"] for f in lista["filas"])

    def test_filtra_por_prioridad_minima(self, cliente_corrido):
        alta = cliente_corrido.get(
            "/api/v1/gestion", params={"prioridad_minima": 4}, headers=CABECERA
        ).json()
        assert all(f["prioridad"] >= 4 for f in alta["filas"])
        assert alta["total"] < cliente_corrido.get(
            "/api/v1/gestion", headers=CABECERA
        ).json()["total"]

    def test_filtra_por_bucket(self, cliente_corrido):
        r = cliente_corrido.get(
            "/api/v1/gestion", params={"bucket": "B07"}, headers=CABECERA
        ).json()
        assert {f["bucket"] for f in r["filas"]} == {"B07"}

    def test_filtra_por_vendedor(self, cliente_corrido):
        r = cliente_corrido.get(
            "/api/v1/gestion", params={"vendedor": "LUIS"}, headers=CABECERA
        ).json()
        assert r["total"] == 1
        assert r["filas"][0]["factura"] == "F-4"

    def test_busca_por_numero_de_factura(self, cliente_corrido):
        r = cliente_corrido.get(
            "/api/v1/gestion", params={"busqueda": "F-6"}, headers=CABECERA
        ).json()
        assert {f["factura"] for f in r["filas"]} == {"F-6"}

    @pytest.mark.parametrize("orden", ["prioridad", "dias", "saldo", "cliente"])
    def test_ordena_por_los_cuatro_criterios_de_82(self, cliente_corrido, orden):
        r = cliente_corrido.get(
            "/api/v1/gestion", params={"orden": orden}, headers=CABECERA
        )
        assert r.status_code == 200

    def test_un_orden_invalido_se_rechaza(self, cliente_corrido):
        r = cliente_corrido.get(
            "/api/v1/gestion", params={"orden": "por_capricho"}, headers=CABECERA
        )
        assert r.status_code == 422

    def test_pagina(self, cliente_corrido):
        primera = cliente_corrido.get(
            "/api/v1/gestion", params={"por_pagina": 2, "pagina": 1}, headers=CABECERA
        ).json()
        segunda = cliente_corrido.get(
            "/api/v1/gestion", params={"por_pagina": 2, "pagina": 2}, headers=CABECERA
        ).json()
        assert len(primera["filas"]) == 2
        assert primera["total"] == segunda["total"]
        assert {f["id"] for f in primera["filas"]} & {f["id"] for f in segunda["filas"]} == set()


class TestDetalleCliente:
    def test_trae_indicadores_y_alertas_en_una_llamada(self, cliente_corrido):
        r = cliente_corrido.get("/api/v1/clientes/900", headers=CABECERA).json()
        assert r["cliente_nit"] == "900"
        assert Decimal(r["cartera_total"]) == Decimal("6000000.00")
        assert r["alertas"]

    def test_un_cliente_inexistente_da_404(self, cliente_corrido):
        r = cliente_corrido.get("/api/v1/clientes/000", headers=CABECERA)
        assert r.status_code == 404
        assert "no tiene cartera" in r.json()["detail"]


class TestConfiguracion:
    def test_muestra_los_buckets_y_las_reglas(self, cliente_corrido):
        c = cliente_corrido.get("/api/v1/configuracion", headers=CABECERA).json()
        assert len(c["buckets"]) == 8
        assert {r["codigo"] for r in c["reglas"]} >= {"R01", "R02", "R06", "A11"}

    def test_marca_las_reglas_pendientes_de_umbral(self, cliente_corrido):
        """§8.4: los parametros sin definir se muestran como tales."""
        c = cliente_corrido.get("/api/v1/configuracion", headers=CABECERA).json()
        r01 = next(r for r in c["reglas"] if r["codigo"] == "R01")
        assert r01["activa"] is False
        assert r01["faltantes"] == ["umbral_saldo_alto"]
        assert "no ha asignado valor" in r01["motivo_inactiva"]

    def test_fijar_el_umbral_activa_la_regla(self, cliente_corrido):
        r = cliente_corrido.put(
            "/api/v1/configuracion/reglas/R01/parametros/umbral_saldo_alto",
            json={"valor": "5000000", "usuario_id": "hbarrera"},
            headers=CABECERA,
        )
        assert r.status_code == 200
        r01 = next(x for x in r.json()["reglas"] if x["codigo"] == "R01")
        assert r01["activa"] is True
        assert r01["parametros"] == {"umbral_saldo_alto": "5000000"}

    def test_el_cambio_queda_en_la_auditoria(self, cliente_corrido):
        cliente_corrido.put(
            "/api/v1/configuracion/reglas/R03/parametros/n_facturas_vencidas",
            json={"valor": "5", "usuario_id": "hbarrera"},
            headers=CABECERA,
        )
        historial = cliente_corrido.get(
            "/api/v1/configuracion/auditoria", headers=CABECERA
        ).json()
        assert historial[0]["usuario_id"] == "hbarrera"
        assert historial[0]["valor_anterior"] == "3"
        assert historial[0]["valor_nuevo"] == "5"

    def test_un_valor_no_numerico_se_rechaza(self, cliente_corrido):
        """Sin esta validacion el motor reventaria en la corrida de madrugada."""
        r = cliente_corrido.put(
            "/api/v1/configuracion/reglas/R01/parametros/umbral_saldo_alto",
            json={"valor": "cinco millones", "usuario_id": "hbarrera"},
            headers=CABECERA,
        )
        assert r.status_code == 422
        assert "Valor invalido" in r.json()["detail"]

    def test_un_valor_negativo_se_rechaza(self, cliente_corrido):
        r = cliente_corrido.put(
            "/api/v1/configuracion/reglas/R06/parametros/dias_preventivos",
            json={"valor": "-5", "usuario_id": "hbarrera"},
            headers=CABECERA,
        )
        assert r.status_code == 422

    def test_un_parametro_que_no_es_de_la_regla_se_rechaza(self, cliente_corrido):
        r = cliente_corrido.put(
            "/api/v1/configuracion/reglas/R06/parametros/umbral_saldo_alto",
            json={"valor": "1000", "usuario_id": "hbarrera"},
            headers=CABECERA,
        )
        assert r.status_code == 400
        assert "no usa el parametro" in r.json()["detail"]

    def test_una_regla_inexistente_da_404(self, cliente_corrido):
        r = cliente_corrido.put(
            "/api/v1/configuracion/reglas/R99/parametros/x",
            json={"valor": "1", "usuario_id": "hbarrera"},
            headers=CABECERA,
        )
        assert r.status_code == 404


class TestEjecucion:
    def test_reprocesar_el_mismo_corte_no_duplica(self, cliente_corrido):
        r = cliente_corrido.post(
            "/api/v1/ejecucion", json={"corte": str(CORTE)}, headers=CABECERA
        ).json()
        assert r["alertas_insertadas"] == 0
        assert r["alertas_actualizadas"] > 0

    def test_informa_que_reglas_no_se_evaluaron(self, cliente_corrido):
        r = cliente_corrido.post(
            "/api/v1/ejecucion", json={"corte": str(CORTE)}, headers=CABECERA
        ).json()
        assert set(r["reglas_inactivas"]) == {"R01", "R02", "A12"}

    def test_la_bitacora_registra_las_corridas(self, cliente_corrido):
        bitacora = cliente_corrido.get("/api/v1/ejecucion", headers=CABECERA).json()
        assert bitacora[0]["estado"] == "ok"
        assert bitacora[0]["filas_procesadas"] == len(CARTERA)

    def test_sin_corte_usa_hoy_en_bogota(self, cliente_corrido):
        """C-11: la zona del motor, no la del servidor."""
        from busint_alertas.core.fechas import hoy

        r = cliente_corrido.post("/api/v1/ejecucion", json={}, headers=CABECERA).json()
        assert r["corte"] == str(hoy())

    def test_un_fallo_del_origen_se_distingue_del_fallo_del_motor(self, fabrica):
        """502 dice: revisa el ERP. 500 diria: revisa el codigo."""
        from fastapi.testclient import TestClient

        from busint_alertas.api import crear_app
        from busint_alertas.fuentes.base import ErrorDeOrigen

        class FuenteCaida:
            def leer(self, empresa_id, corte):
                raise ErrorDeOrigen("el ERP no responde")

        c = TestClient(crear_app(fabrica, fuente=FuenteCaida()))
        r = c.post("/api/v1/ejecucion", json={"corte": str(CORTE)}, headers=CABECERA)
        assert r.status_code == 502
        assert "el ERP no responde" in r.json()["detail"]


class TestNombreDelCliente:
    """Una bandeja de trabajo con solo NIT obliga a buscar a quien se llama."""

    def test_la_lista_trae_el_nombre(self, cliente_corrido):
        from .conftest import CABECERA

        lista = cliente_corrido.get("/api/v1/gestion", headers=CABECERA).json()
        assert all(f["cliente_nombre"] == "Cliente Demo" for f in lista["filas"])

    def test_el_detalle_tambien(self, cliente_corrido):
        from .conftest import CABECERA

        d = cliente_corrido.get("/api/v1/clientes/900", headers=CABECERA).json()
        assert all(a["cliente_nombre"] == "Cliente Demo" for a in d["alertas"])

    def test_no_hace_una_consulta_por_fila(self, cliente_corrido, contar_consultas):
        """El mapa de nombres se trae de una vez: son tantas filas como
        clientes, no como alertas."""
        cliente_corrido.get("/api/v1/gestion", headers=CABECERA)
        assert contar_consultas("ar_riesgo_cliente") == 1
