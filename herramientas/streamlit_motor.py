#!/usr/bin/env python3
"""Banco de pruebas del motor, sobre el motor Python real.

    pip install -e ".[dev]" streamlit
    streamlit run herramientas/streamlit_motor.py

A diferencia de la pagina publicada, esta version **importa el motor de
verdad**: `busint_alertas.motores.cartera`. No hay port ni copia de las reglas,
asi que es la version a la que hay que creerle si las dos discrepan alguna vez.

Trabaja en memoria y no toca base de datos: es un banco de pruebas del motor de
reglas, no del sistema completo. Para el sistema entero, con persistencia, API,
roles y panel, esta `herramientas/servidor_demo.py`.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from busint_alertas.core.motor import ContextoEjecucion  # noqa: E402
from busint_alertas.core.tipos import FASE_VIGENTE  # noqa: E402
from busint_alertas.motores.cartera import (  # noqa: E402
    ConfiguracionCartera, Movimiento, MotorCartera,
)
from busint_alertas.motores.cartera.configuracion import BUCKETS_BUSINT  # noqa: E402
from busint_alertas.motores.cartera.historial import HistorialGestion  # noqa: E402
from busint_alertas.motores.cartera.reglas import REGLAS  # noqa: E402

EMPRESA = "E01"
CORTE_INICIAL = date(2026, 8, 21)
GESTION_DESDE = date(2026, 6, 1)

CLIENTES = {
    "900111": "DISTRIBUIDORA DEL NORTE SAS",
    "900222": "AGROINDUSTRIA DEL VALLE SAS",
}

#: Cartera de ejemplo. Elegida para que, moviendo el corte, dispare el catalogo
#: completo. F-109 trae nota credito sin aplicar (C-10) y F-110 saldo negativo,
#: que nunca es mora (§5.3, caso T09).
CARTERA = [
    ("F-101", "900111", date(2026, 9, 20), "4200000", "0"),
    ("F-102", "900111", date(2026, 9, 5), "2800000", "0"),
    ("F-103", "900111", date(2026, 8, 21), "9500000", "0"),
    ("F-104", "900111", date(2026, 8, 6), "1750000", "0"),
    ("F-105", "900111", date(2026, 7, 7), "12400000", "0"),
    ("F-106", "900111", date(2026, 6, 2), "5800000", "0"),
    ("F-107", "900111", date(2026, 4, 3), "3200000", "0"),
    ("F-108", "900111", date(2026, 2, 2), "8600000", "0"),
    ("F-109", "900111", date(2026, 9, 12), "3000000", "2500000"),
    ("F-110", "900111", date(2026, 3, 1), "-900000", "0"),
    ("F-201", "900222", date(2026, 8, 14), "26500000", "0"),
    ("F-202", "900222", date(2026, 7, 20), "1200000", "0"),
    ("F-203", "900222", date(2026, 5, 15), "4800000", "0"),
]

UMBRALES = (
    ("dias_preventivos", "Días preventivos", "R06 · avisa antes de vencer", "15"),
    ("n_facturas_vencidas", "N facturas vencidas", "R03 · cliente reincidente", "3"),
    ("pct_mayor_90_umbral", "% cartera > 90 días", "A11 · envejecimiento crítico", "40"),
    ("umbral_saldo_alto", "Umbral saldo alto", "R01 · eleva la prioridad", ""),
    ("umbral_saldo_critico", "Umbral saldo crítico", "R02 · alta exposición", ""),
    ("dias_sin_gestion", "Días sin gestión", "A12 · escalar al responsable", ""),
)

st.set_page_config(page_title="Motor de alertas de cartera", layout="wide")


def cartera_inicial() -> pd.DataFrame:
    return pd.DataFrame([
        {"factura": f, "cliente": c, "vencimiento": v,
         "saldo": float(s), "nota_credito": float(cr)}
        for f, c, v, s, cr in CARTERA
    ])


def a_movimientos(df: pd.DataFrame) -> list[Movimiento]:
    """Convierte la tabla en movimientos, saltando las filas incompletas.

    Una fila a medio escribir en el editor no debe tumbar la pagina entera.
    """
    movimientos = []
    for _, fila in df.iterrows():
        if pd.isna(fila.get("vencimiento")) or not str(fila.get("factura", "")).strip():
            continue
        vence = pd.to_datetime(fila["vencimiento"]).date()
        nit = str(fila["cliente"]).strip()
        movimientos.append(Movimiento(
            empresa_id=EMPRESA, cliente_nit=nit,
            factura=str(fila["factura"]).strip(),
            fecha_emision=vence - timedelta(days=30), fecha_vencimiento=vence,
            saldo=Decimal(str(fila["saldo"] or 0)),
            valor_credito=Decimal(str(fila.get("nota_credito") or 0)),
            cliente_nombre=CLIENTES.get(nit, nit),
        ))
    return movimientos


def pesos(v) -> str:
    return f"$ {float(v):,.0f}".replace(",", ".")


st.title("Banco de pruebas del motor de cartera")
st.caption(
    "Corre el motor Python real: `busint_alertas.motores.cartera`. "
    "No hay copia de las reglas."
)

with st.sidebar:
    st.subheader("Fecha de corte")
    corte = st.date_input("Corte", value=CORTE_INICIAL, label_visibility="collapsed")

    st.subheader("Umbrales")
    st.caption("Déjalos vacíos para desactivar la regla (C-05).")
    parametros: dict[str, object] = {}
    for clave, titulo, pista, defecto in UMBRALES:
        crudo = st.text_input(titulo, value=defecto, help=pista, key=clave).strip()
        if not crudo:
            continue
        try:
            parametros[clave] = (
                int(crudo) if clave.startswith(("dias_", "n_")) else Decimal(crudo)
            )
        except (ValueError, InvalidOperation):
            st.warning(f"«{crudo}» no es un número; {clave} queda sin asignar.")

st.subheader("Cartera")
st.caption("Edita las celdas, añade filas o bórralas: el motor recalcula al instante.")
editada = st.data_editor(
    cartera_inicial(), num_rows="dynamic", use_container_width=True,
    column_config={
        "factura": st.column_config.TextColumn("Factura", width="small"),
        "cliente": st.column_config.TextColumn("Cliente", width="small"),
        "vencimiento": st.column_config.DateColumn("Vencimiento", format="DD/MM/YYYY"),
        "saldo": st.column_config.NumberColumn("Saldo", format="%.2f"),
        "nota_credito": st.column_config.NumberColumn("Nota crédito", format="%.2f"),
    },
)

movimientos = a_movimientos(editada)
config = ConfiguracionCartera.plantilla(EMPRESA, **parametros)
historial = HistorialGestion(
    ultima_gestion={},
    alerta_desde={(m.cliente_nit, m.factura): GESTION_DESDE for m in movimientos},
)
resultado = MotorCartera().evaluar(
    ContextoEjecucion(EMPRESA, corte, config, fase_vigente=FASE_VIGENTE,
                      historial=historial),
    movimientos,
)
g = resultado.indicadores["globales"]

st.subheader("Indicadores")
for col, (etiqueta, valor) in zip(st.columns(5), [
    ("Cartera total", g["cartera_total"]), ("Por vencer", g["por_vencer"]),
    ("Vence hoy", g["vence_hoy"]), ("Vencida", g["vencida"]),
    ("Más de 90 días", g["mayor_90"]),
]):
    total = g["cartera_total"] or 1
    col.metric(
        etiqueta, pesos(valor),
        delta=None if etiqueta == "Cartera total"
        else f"{float(valor) / float(total) * 100:.1f} % del total",
        delta_color="off",
    )

izquierda, derecha = st.columns([1.3, 1])

with izquierda:
    st.subheader("Antigüedad")
    aging = pd.DataFrame([
        {"Rango": b.etiqueta,
         "Saldo": float(g["por_bucket"].get(b.codigo, 0)),
         "Facturas": g["facturas_por_bucket"].get(b.codigo, 0)}
        for b in BUCKETS_BUSINT
    ])
    st.bar_chart(aging.set_index("Rango")["Saldo"], height=220)
    st.dataframe(aging, use_container_width=True, hide_index=True)

with derecha:
    st.subheader(f"Qué disparó · {len(resultado.alertas)}")
    if not resultado.alertas:
        st.info("Ninguna alerta con esta cartera y estos umbrales.")
    for a in sorted(resultado.alertas, key=lambda x: (-x.prioridad.value, x.codigo)):
        with st.container(border=True):
            st.markdown(
                f"**{a.codigo}** {a.etiqueta} · `{a.prioridad.etiqueta}`"
                f" — {a.entidad or 'del cliente'}"
            )
            st.caption(str(a.explicacion))
            for e in a.datos.get("elevada_por", []):
                st.caption(f"prioridad elevada · {e}")
            st.caption(f"→ {a.accion}")

st.subheader("Riesgo por cliente")
marcadores: dict[str, list[str]] = {}
for m in resultado.marcadores:
    marcadores.setdefault(m.sujeto, []).append(f"{m.codigo} {m.etiqueta}")

if resultado.indicadores["clientes"]:
    st.dataframe(
        pd.DataFrame([
            {"Cliente": p.cliente_nombre, "NIT": nit,
             "Cartera": float(p.cartera_total), "% vencida": float(p.pct_vencida),
             "% > 90": float(p.pct_90), "Días máx": p.dias_max,
             "Vencidas": f"{p.n_vencidas} de {p.n_facturas}",
             "Prioridad": p.prioridad.etiqueta,
             "Marcadores": ", ".join(marcadores.get(nit, [])) or "—"}
            for nit, p in resultado.indicadores["clientes"].items()
        ]),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("Ningún cliente con saldo deudor.")

no_deudores = resultado.indicadores.get("saldos_no_deudores") or []
if no_deudores:
    st.caption(
        "Saldos que no son deuda y por tanto no se clasifican como mora (§5.3): "
        + ", ".join(
            f"{f} de {c} ({tipo.replace('_', ' ')})" for c, f, _, tipo in no_deudores
        )
    )

st.subheader("Reglas")
columnas = st.columns(4)
for i, regla in enumerate(REGLAS):
    motivo = resultado.reglas_inactivas.get(regla.codigo)
    with columnas[i % 4].container(border=True):
        st.markdown(
            f"{'🟢' if motivo is None else '⚪️'} **{regla.codigo}** {regla.etiqueta}"
        )
        st.caption(
            f"ámbito {regla.ambito} · "
            + (f"emite {regla.alerta}" if regla.alerta
               else f"marca {regla.marcador}" if regla.marcador
               else f"eleva la prioridad {regla.eleva_prioridad} nivel")
        )
        if motivo:
            st.caption(motivo)
