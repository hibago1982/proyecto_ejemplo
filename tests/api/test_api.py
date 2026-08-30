"""API REST: contrato, panel, lista de gestion, detalle y configuracion."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .conftest import CARTERA, CORTE, EMPRESA, entrar


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

    def test_los_montos_son_cadena_y_no_numero(self, cliente_corrido, CABECERA):
        """C-09: un float de JavaScript no representa 1234567.89 sin error."""
        contrato = cliente_corrido.get("/openapi.json").json()
        kpi = contrato["components"]["schemas"]["TarjetaKPI"]["properties"]
        assert kpi["valor"]["type"] == "string"

        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        assert isinstance(panel["kpis"][0]["valor"], str)

    def test_la_sonda_de_salud_responde(self, cliente):
        assert cliente.get("/salud").json() == {"estado": "ok"}


class TestAutenticacion:
    """§8.4 y C-13. Hasta la etapa 7 la empresa llegaba en una cabecera que el
    cliente controlaba; cualquiera podia leer y escribir en la cartera ajena."""

    def test_sin_token_no_se_entra(self, cliente_corrido):
        r = cliente_corrido.get("/api/v1/panel")
        assert r.status_code == 401
        assert r.headers["WWW-Authenticate"] == "Bearer"

    def test_un_token_manipulado_se_rechaza(self, cliente_corrido, CABECERA):
        token = CABECERA["Authorization"].removeprefix("Bearer ")
        crudo, firma = token.split(".")
        falso = {"Authorization": f"Bearer {crudo}.{firma[:-2]}xx"}
        r = cliente_corrido.get("/api/v1/panel", headers=falso)
        assert r.status_code == 401
        assert "firma" in r.json()["detail"]

    def test_no_se_puede_pedir_la_cartera_de_otra_empresa(self, cliente_corrido):
        """El intruso es administrador, pero de la empresa E99."""
        r = cliente_corrido.get("/api/v1/panel", headers=entrar(cliente_corrido, "intruso"))
        assert r.status_code == 404
        assert "E99" in r.json()["detail"]

    def test_credenciales_incorrectas_no_dicen_que_parte_fallo(self, cliente):
        sin_usuario = cliente.post(
            "/api/v1/sesion", json={"usuario": "fantasma", "clave": "x"}
        )
        mala_clave = cliente.post(
            "/api/v1/sesion", json={"usuario": "admin", "clave": "incorrecta"}
        )
        assert sin_usuario.status_code == mala_clave.status_code == 401
        assert sin_usuario.json()["detail"] == mala_clave.json()["detail"]

    def test_la_sesion_dice_quien_soy(self, cliente_corrido, CABECERA):
        r = cliente_corrido.get("/api/v1/sesion", headers=CABECERA).json()
        assert r["usuario_id"] == "admin"
        assert r["empresa_id"] == "E01"
        assert r["rol_etiqueta"] == "Administrador"


class TestRoles:
    """C-13: los permisos son acumulativos y cada endpoint declara su suelo."""

    def test_consulta_puede_leer(self, cliente_corrido):
        r = cliente_corrido.get("/api/v1/panel", headers=entrar(cliente_corrido, "ana"))
        assert r.status_code == 200

    def test_consulta_no_puede_gestionar(self, cliente_corrido):
        r = cliente_corrido.post(
            "/api/v1/clientes/900/gestiones",
            json={"factura": "F-4", "tipo": "llamada"},
            headers=entrar(cliente_corrido, "ana"),
        )
        assert r.status_code == 403
        assert "Gestor de cartera" in r.json()["detail"]

    def test_gestor_puede_gestionar(self, cliente_corrido):
        r = cliente_corrido.post(
            "/api/v1/clientes/900/gestiones",
            json={"factura": "F-4", "tipo": "llamada"},
            headers=entrar(cliente_corrido, "gestor"),
        )
        assert r.status_code == 201

    def test_gestor_no_puede_ejecutar_el_motor(self, cliente_corrido):
        r = cliente_corrido.post(
            "/api/v1/ejecucion", json={"corte": str(CORTE)},
            headers=entrar(cliente_corrido, "gestor"),
        )
        assert r.status_code == 403
        assert "Coordinador" in r.json()["detail"]

    def test_coordinador_puede_ejecutar(self, cliente_corrido):
        r = cliente_corrido.post(
            "/api/v1/ejecucion", json={"corte": str(CORTE)},
            headers=entrar(cliente_corrido, "coord"),
        )
        assert r.status_code == 200

    def test_coordinador_no_puede_cambiar_umbrales(self, cliente_corrido):
        r = cliente_corrido.put(
            "/api/v1/configuracion/reglas/R03/parametros/n_facturas_vencidas",
            json={"valor": "5"}, headers=entrar(cliente_corrido, "coord"),
        )
        assert r.status_code == 403
        assert "Administrador" in r.json()["detail"]

    def test_administrador_puede_todo(self, cliente_corrido, CABECERA):
        assert cliente_corrido.get("/api/v1/panel", headers=CABECERA).status_code == 200
        assert cliente_corrido.put(
            "/api/v1/configuracion/reglas/R03/parametros/n_facturas_vencidas",
            json={"valor": "5"}, headers=CABECERA,
        ).status_code == 200


class TestPanel:
    def test_los_kpis_cuadran_con_la_identidad_de_cartera(self, cliente_corrido, CABECERA):
        """C-14: total = por vencer + vence hoy + vencida."""
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        kpis = {k["codigo"]: Decimal(k["valor"]) for k in panel["kpis"]}
        assert (
            kpis["por_vencer"] + kpis["vence_hoy"] + kpis["vencida"]
            == kpis["cartera_total"]
        )

    def test_el_aging_incluye_el_bucket_por_vencer(self, cliente_corrido, CABECERA):
        """B00 no emite alerta: si el aging saliera de ar_alerta, faltaria."""
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        b00 = next(b for b in panel["aging"] if b["bucket"] == "B00")
        assert Decimal(b00["saldo"]) == Decimal("1000000.00")

    def test_el_aging_trae_los_ocho_buckets(self, cliente_corrido, CABECERA):
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        assert [b["bucket"] for b in panel["aging"]] == [f"B0{i}" for i in range(8)]

    def test_los_porcentajes_los_calcula_el_servidor(self, cliente_corrido, CABECERA):
        """§16: una sola fuente de calculo, tambien para los indicadores."""
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        total = next(k for k in panel["kpis"] if k["codigo"] == "cartera_total")
        assert total["pct_sobre_total"] == "100.00"

    def test_el_corte_por_defecto_es_el_ultimo_calculado(self, cliente_corrido, CABECERA):
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        assert panel["corte"] == str(CORTE)

    def test_se_listan_los_cortes_disponibles(self, cliente_corrido, CABECERA):
        cortes = cliente_corrido.get("/api/v1/cortes", headers=CABECERA).json()
        assert len(cortes) == 1
        assert cortes[0]["corte"] == str(CORTE)
        assert cortes[0]["n_clientes"] == 1


class TestListaGestion:
    def test_devuelve_las_alertas_del_corte(self, cliente_corrido, CABECERA):
        lista = cliente_corrido.get("/api/v1/gestion", headers=CABECERA).json()
        assert lista["total"] > 0
        assert lista["filas"]

    def test_cada_fila_explica_por_que_esta_ahi(self, cliente_corrido, CABECERA):
        """§7.4: sin explicacion, el semaforo no es defendible."""
        lista = cliente_corrido.get("/api/v1/gestion", headers=CABECERA).json()
        assert all(f["explicacion"] for f in lista["filas"])

    def test_filtra_por_prioridad_minima(self, cliente_corrido, CABECERA):
        alta = cliente_corrido.get(
            "/api/v1/gestion", params={"prioridad_minima": 4}, headers=CABECERA
        ).json()
        assert all(f["prioridad"] >= 4 for f in alta["filas"])
        assert alta["total"] < cliente_corrido.get(
            "/api/v1/gestion", headers=CABECERA
        ).json()["total"]

    def test_filtra_por_bucket(self, cliente_corrido, CABECERA):
        r = cliente_corrido.get(
            "/api/v1/gestion", params={"bucket": "B07"}, headers=CABECERA
        ).json()
        assert {f["bucket"] for f in r["filas"]} == {"B07"}

    def test_filtra_por_vendedor(self, cliente_corrido, CABECERA):
        r = cliente_corrido.get(
            "/api/v1/gestion", params={"vendedor": "LUIS"}, headers=CABECERA
        ).json()
        assert r["total"] == 1
        assert r["filas"][0]["factura"] == "F-4"

    def test_busca_por_numero_de_factura(self, cliente_corrido, CABECERA):
        r = cliente_corrido.get(
            "/api/v1/gestion", params={"busqueda": "F-6"}, headers=CABECERA
        ).json()
        assert {f["factura"] for f in r["filas"]} == {"F-6"}

    @pytest.mark.parametrize("orden", ["prioridad", "dias", "saldo", "cliente"])
    def test_ordena_por_los_cuatro_criterios_de_82(self, cliente_corrido, orden, CABECERA):
        r = cliente_corrido.get(
            "/api/v1/gestion", params={"orden": orden}, headers=CABECERA
        )
        assert r.status_code == 200

    def test_un_orden_invalido_se_rechaza(self, cliente_corrido, CABECERA):
        r = cliente_corrido.get(
            "/api/v1/gestion", params={"orden": "por_capricho"}, headers=CABECERA
        )
        assert r.status_code == 422

    def test_pagina(self, cliente_corrido, CABECERA):
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
    def test_trae_indicadores_y_alertas_en_una_llamada(self, cliente_corrido, CABECERA):
        r = cliente_corrido.get("/api/v1/clientes/900", headers=CABECERA).json()
        assert r["cliente_nit"] == "900"
        assert Decimal(r["cartera_total"]) == Decimal("6000000.00")
        assert r["alertas"]

    def test_un_cliente_inexistente_da_404(self, cliente_corrido, CABECERA):
        r = cliente_corrido.get("/api/v1/clientes/000", headers=CABECERA)
        assert r.status_code == 404
        assert "no tiene cartera" in r.json()["detail"]


class TestConfiguracion:
    def test_muestra_los_buckets_y_las_reglas(self, cliente_corrido, CABECERA):
        c = cliente_corrido.get("/api/v1/configuracion", headers=CABECERA).json()
        assert len(c["buckets"]) == 8
        assert {r["codigo"] for r in c["reglas"]} >= {"R01", "R02", "R06", "A11"}

    def test_marca_las_reglas_pendientes_de_umbral(self, cliente_corrido, CABECERA):
        """§8.4: los parametros sin definir se muestran como tales."""
        c = cliente_corrido.get("/api/v1/configuracion", headers=CABECERA).json()
        r01 = next(r for r in c["reglas"] if r["codigo"] == "R01")
        assert r01["activa"] is False
        assert r01["faltantes"] == ["umbral_saldo_alto"]
        assert "no ha asignado valor" in r01["motivo_inactiva"]

    def test_fijar_el_umbral_activa_la_regla(self, cliente_corrido, CABECERA):
        r = cliente_corrido.put(
            "/api/v1/configuracion/reglas/R01/parametros/umbral_saldo_alto",
            json={"valor": "5000000"},
            headers=CABECERA,
        )
        assert r.status_code == 200
        r01 = next(x for x in r.json()["reglas"] if x["codigo"] == "R01")
        assert r01["activa"] is True
        assert r01["parametros"] == {"umbral_saldo_alto": "5000000"}

    def test_el_cambio_queda_en_la_auditoria(self, cliente_corrido, CABECERA):
        cliente_corrido.put(
            "/api/v1/configuracion/reglas/R03/parametros/n_facturas_vencidas",
            json={"valor": "5"},
            headers=CABECERA,
        )
        historial = cliente_corrido.get(
            "/api/v1/configuracion/auditoria", headers=CABECERA
        ).json()
        # §10.3: el usuario sale del token, no del cuerpo de la peticion.
        assert historial[0]["usuario_id"] == "admin"
        assert historial[0]["valor_anterior"] == "3"
        assert historial[0]["valor_nuevo"] == "5"

    def test_un_valor_no_numerico_se_rechaza(self, cliente_corrido, CABECERA):
        """Sin esta validacion el motor reventaria en la corrida de madrugada."""
        r = cliente_corrido.put(
            "/api/v1/configuracion/reglas/R01/parametros/umbral_saldo_alto",
            json={"valor": "cinco millones"},
            headers=CABECERA,
        )
        assert r.status_code == 422
        assert "Valor invalido" in r.json()["detail"]

    def test_un_valor_negativo_se_rechaza(self, cliente_corrido, CABECERA):
        r = cliente_corrido.put(
            "/api/v1/configuracion/reglas/R06/parametros/dias_preventivos",
            json={"valor": "-5"},
            headers=CABECERA,
        )
        assert r.status_code == 422

    def test_un_parametro_que_no_es_de_la_regla_se_rechaza(self, cliente_corrido, CABECERA):
        r = cliente_corrido.put(
            "/api/v1/configuracion/reglas/R06/parametros/umbral_saldo_alto",
            json={"valor": "1000"},
            headers=CABECERA,
        )
        assert r.status_code == 400
        assert "no usa el parametro" in r.json()["detail"]

    def test_una_regla_inexistente_da_404(self, cliente_corrido, CABECERA):
        r = cliente_corrido.put(
            "/api/v1/configuracion/reglas/R99/parametros/x",
            json={"valor": "1"},
            headers=CABECERA,
        )
        assert r.status_code == 404


class TestEjecucion:
    def test_reprocesar_el_mismo_corte_no_duplica(self, cliente_corrido, CABECERA):
        r = cliente_corrido.post(
            "/api/v1/ejecucion", json={"corte": str(CORTE)}, headers=CABECERA
        ).json()
        assert r["alertas_insertadas"] == 0
        assert r["alertas_actualizadas"] > 0

    def test_informa_que_reglas_no_se_evaluaron(self, cliente_corrido, CABECERA):
        r = cliente_corrido.post(
            "/api/v1/ejecucion", json={"corte": str(CORTE)}, headers=CABECERA
        ).json()
        assert set(r["reglas_inactivas"]) == {"R01", "R02", "A12"}

    def test_la_bitacora_registra_las_corridas(self, cliente_corrido, CABECERA):
        bitacora = cliente_corrido.get("/api/v1/ejecucion", headers=CABECERA).json()
        assert bitacora[0]["estado"] == "ok"
        assert bitacora[0]["filas_procesadas"] == len(CARTERA)

    def test_sin_corte_usa_hoy_en_bogota(self, cliente_corrido, CABECERA):
        """C-11: la zona del motor, no la del servidor."""
        from busint_alertas.core.fechas import hoy

        r = cliente_corrido.post("/api/v1/ejecucion", json={}, headers=CABECERA).json()
        assert r["corte"] == str(hoy())

    def test_un_fallo_del_origen_se_distingue_del_fallo_del_motor(self, fabrica, CABECERA):
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

    def test_la_lista_trae_el_nombre(self, cliente_corrido, CABECERA):
        lista = cliente_corrido.get("/api/v1/gestion", headers=CABECERA).json()
        assert all(f["cliente_nombre"] == "Cliente Demo" for f in lista["filas"])

    def test_el_detalle_tambien(self, cliente_corrido, CABECERA):
        d = cliente_corrido.get("/api/v1/clientes/900", headers=CABECERA).json()
        assert all(a["cliente_nombre"] == "Cliente Demo" for a in d["alertas"])

    def test_no_hace_una_consulta_por_fila(self, cliente_corrido, contar_consultas, CABECERA):
        """El mapa de nombres se trae de una vez: son tantas filas como
        clientes, no como alertas."""
        cliente_corrido.get("/api/v1/gestion", headers=CABECERA)
        assert contar_consultas("ar_riesgo_cliente") == 1


class TestGestionPorApi:
    """§11: el flujo de cobranza de principio a fin, por el API."""

    def _registrar(self, cliente, cabecera, **cambios):
        cuerpo = {"factura": "F-4", "tipo": "llamada", "resultado": "Contactado"}
        cuerpo.update(cambios)
        return cliente.post(
            "/api/v1/clientes/900/gestiones", json=cuerpo, headers=cabecera
        )

    def test_registrar_devuelve_201(self, cliente_corrido, CABECERA):
        r = self._registrar(cliente_corrido, CABECERA)
        assert r.status_code == 201
        # El usuario lo pone el token; el cliente no puede firmar por otro.
        assert r.json()["usuario_id"] == "admin"

    def test_la_alerta_queda_gestionada(self, cliente_corrido, CABECERA):
        self._registrar(cliente_corrido, CABECERA)
        d = cliente_corrido.get("/api/v1/clientes/900", headers=CABECERA).json()
        de_f4 = [a for a in d["alertas"] if a["factura"] == "F-4"]
        assert de_f4 and all(a["estado"] == "gestionada" for a in de_f4)

    def test_el_detalle_trae_el_historial(self, cliente_corrido, CABECERA):
        self._registrar(cliente_corrido, CABECERA, resultado="Primera")
        self._registrar(cliente_corrido, CABECERA, resultado="Segunda")
        d = cliente_corrido.get("/api/v1/clientes/900", headers=CABECERA).json()
        assert len(d["gestiones"]) == 2

    def test_se_guarda_el_compromiso_de_pago(self, cliente_corrido, CABECERA):
        r = self._registrar(cliente_corrido, CABECERA, tipo="acuerdo",
            compromiso_fecha="2026-09-15", compromiso_valor="500000",
        )
        assert r.status_code == 201
        assert r.json()["compromiso_valor"] == "500000.00"

    def test_un_compromiso_a_medias_se_rechaza(self, cliente_corrido, CABECERA):
        r = self._registrar(cliente_corrido, CABECERA, compromiso_fecha="2026-09-15")
        assert r.status_code == 422
        assert "Falta el valor" in r.json()["detail"]

    def test_un_tipo_invalido_dice_cuales_valen(self, cliente_corrido, CABECERA):
        r = self._registrar(cliente_corrido, CABECERA, tipo="telepatia")
        assert r.status_code == 422
        assert "llamada" in r.json()["detail"]

    def test_una_factura_sin_alerta_se_rechaza(self, cliente_corrido, CABECERA):
        r = self._registrar(cliente_corrido, CABECERA, factura="F-999")
        assert r.status_code == 422
        assert "No hay alertas de la factura" in r.json()["detail"]

    def test_gestionar_no_altera_el_saldo(self, cliente_corrido, CABECERA):
        """§16: el estado de la gestión no toca el estado de la factura."""
        antes = cliente_corrido.get("/api/v1/clientes/900", headers=CABECERA).json()
        saldo = next(a["saldo"] for a in antes["alertas"] if a["factura"] == "F-4")

        self._registrar(cliente_corrido, CABECERA)

        despues = cliente_corrido.get("/api/v1/clientes/900", headers=CABECERA).json()
        assert next(a["saldo"] for a in despues["alertas"] if a["factura"] == "F-4") == saldo


class TestFaseVigenteUnica:
    """Una sola definicion de que fase esta desplegada.

    Estuvo repetida en tres sitios y se desincronizo: el motor evaluaba A12
    mientras el panel la anunciaba como bloqueada por fase. El usuario veia en
    pantalla que una regla no se evalua y sus alertas en la lista.
    """

    def test_el_panel_y_la_corrida_coinciden(self, cliente_corrido, CABECERA):
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        corrida = cliente_corrido.post(
            "/api/v1/ejecucion", json={"corte": str(CORTE)}, headers=CABECERA
        ).json()
        assert set(panel["reglas_inactivas"]) == set(corrida["reglas_inactivas"])

    def test_la_configuracion_dice_lo_mismo(self, cliente_corrido, CABECERA):
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        config = cliente_corrido.get("/api/v1/configuracion", headers=CABECERA).json()
        inactivas = {r["codigo"] for r in config["reglas"] if not r["activa"]}
        assert inactivas == set(panel["reglas_inactivas"])

    def test_ninguna_regla_se_declara_bloqueada_por_fase(
        self, cliente_corrido, CABECERA
    ):
        """La fase 5 esta desplegada: A12 solo puede faltarle el umbral."""
        panel = cliente_corrido.get("/api/v1/panel", headers=CABECERA).json()
        assert not any(
            "fase" in motivo.lower() for motivo in panel["reglas_inactivas"].values()
        ), panel["reglas_inactivas"]
