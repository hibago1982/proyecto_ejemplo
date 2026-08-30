#!/usr/bin/env python3
"""Genera los datos del banco de pruebas del motor.

La pagina de pruebas NO reimplementa las reglas: eso duplicaria la logica de
alerta y contradiria §16, ademas de arriesgarse a ensenar un comportamiento que
el motor real no tiene. Lo que hace este script es correr el motor de verdad
sobre una malla de escenarios y volcar su salida, para que la pagina sea un
visor de resultados reales y no una imitacion.

    python herramientas/generar_banco_pruebas.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from busint_alertas.core.motor import ContextoEjecucion  # noqa: E402
from busint_alertas.core.tipos import FASE_VIGENTE  # noqa: E402
from busint_alertas.motores.cartera import (  # noqa: E402
    ConfiguracionCartera, Movimiento, MotorCartera,
)
from busint_alertas.motores.cartera.configuracion import BUCKETS_BUSINT  # noqa: E402
from busint_alertas.motores.cartera.historial import HistorialGestion  # noqa: E402
from busint_alertas.motores.cartera.reglas import REGLAS  # noqa: E402

DESTINO = RAIZ / "banco_pruebas" / "datos.json"
EMPRESA = "E01"

#: Cartera de prueba. Las fechas de vencimiento son fijas: lo que se mueve es la
#: fecha de corte, que es como se comporta el sistema real y lo que permite ver
#: una misma factura recorrer todos los buckets.
CARTERA = [
    # (factura, cliente, vencimiento, saldo, credito, vendedor, zona)
    ("F-101", "900111", date(2026, 9, 20), "4200000", "0"),
    ("F-102", "900111", date(2026, 9, 5), "2800000", "0"),
    ("F-103", "900111", date(2026, 8, 21), "9500000", "0"),
    ("F-104", "900111", date(2026, 8, 6), "1750000", "0"),
    ("F-105", "900111", date(2026, 7, 7), "12400000", "0"),
    ("F-106", "900111", date(2026, 6, 2), "5800000", "0"),
    ("F-107", "900111", date(2026, 4, 3), "3200000", "0"),
    ("F-108", "900111", date(2026, 2, 2), "8600000", "0"),
    # Con nota credito sin aplicar: se netea contra la mas antigua (C-10).
    ("F-109", "900111", date(2026, 9, 12), "3000000", "2500000"),
    # Saldo negativo: credito a favor, nunca mora (§5.3, T09).
    ("F-110", "900111", date(2026, 3, 1), "-900000", "0"),
    ("F-201", "900222", date(2026, 8, 14), "26500000", "0"),
    ("F-202", "900222", date(2026, 7, 20), "1200000", "0"),
    ("F-203", "900222", date(2026, 5, 15), "4800000", "0"),
]

NOMBRES = {
    "900111": "DISTRIBUIDORA DEL NORTE SAS",
    "900222": "AGROINDUSTRIA DEL VALLE SAS",
}

VENDEDORES = {"900111": ("ANA MARIA RESTREPO", "NACIONAL"),
              "900222": ("CARLOS ANDRES MEJIA", "EJE CAFETERO")}

#: Configuraciones que la empresa podria fijar. La primera es el estado real de
#: hoy: R01 y R02 sin umbral, y por tanto inactivas (C-05, §16).
PRESETS = [
    {
        "id": "hoy",
        "nombre": "Como está hoy",
        "detalle": "R01, R02 y A12 sin umbral asignado: el motor no las evalúa.",
        "parametros": {
            "dias_preventivos": 15,
            "n_facturas_vencidas": 3,
            "pct_mayor_90_umbral": Decimal("40"),
        },
    },
    {
        "id": "conservador",
        "nombre": "Conservador",
        "detalle": "Avisa tarde y solo ante montos grandes.",
        "parametros": {
            "dias_preventivos": 7,
            "n_facturas_vencidas": 5,
            "pct_mayor_90_umbral": Decimal("60"),
            "umbral_saldo_alto": Decimal("9000000"),
            "umbral_saldo_critico": Decimal("25000000"),
            "dias_sin_gestion": 45,
        },
    },
    {
        "id": "estricto",
        "nombre": "Estricto",
        "detalle": "Avisa pronto y baja los montos: muchas más alertas.",
        "parametros": {
            "dias_preventivos": 30,
            "n_facturas_vencidas": 2,
            "pct_mayor_90_umbral": Decimal("20"),
            "umbral_saldo_alto": Decimal("3000000"),
            "umbral_saldo_critico": Decimal("8000000"),
            "dias_sin_gestion": 20,
        },
    },
]

#: Cortes semanales. Barrerlos es lo que hace visible el aging en movimiento.
PRIMER_CORTE = date(2026, 6, 1)
CORTES = [PRIMER_CORTE + timedelta(days=7 * i) for i in range(32)]

#: Gestion registrada sobre una factura, para que A12 tenga contra que evaluarse.
GESTIONES = {("900111", "F-105"): date(2026, 8, 1)}


def movimientos() -> list[Movimiento]:
    filas = []
    for factura, nit, vence, saldo, credito in CARTERA:
        vendedor, zona = VENDEDORES[nit]
        filas.append(
            Movimiento(
                empresa_id=EMPRESA, cliente_nit=nit, factura=factura,
                fecha_emision=vence - timedelta(days=30), fecha_vencimiento=vence,
                saldo=Decimal(saldo), valor_credito=Decimal(credito),
                cliente_nombre=NOMBRES[nit], vendedor=vendedor, zona=zona,
            )
        )
    return filas


def historial() -> HistorialGestion:
    return HistorialGestion(
        ultima_gestion=dict(GESTIONES),
        alerta_desde={
            (nit, fac): PRIMER_CORTE for fac, nit, *_ in CARTERA
        },
    )


def evaluar(corte: date, preset: dict) -> dict:
    config = ConfiguracionCartera.plantilla(EMPRESA, **preset["parametros"])
    resultado = MotorCartera().evaluar(
        ContextoEjecucion(
            empresa_id=EMPRESA, corte=corte, configuracion=config,
            fase_vigente=FASE_VIGENTE, historial=historial(),
        ),
        movimientos(),
    )

    globales = resultado.indicadores["globales"]
    alertas = [
        {
            "codigo": a.codigo, "etiqueta": a.etiqueta,
            "prioridad": a.prioridad.value, "prioridad_etiqueta": a.prioridad.etiqueta,
            "accion": a.accion, "cliente": a.sujeto, "factura": a.entidad,
            "explicacion": str(a.explicacion) if a.explicacion else "",
            "bucket": a.datos.get("bucket"),
            "dias": a.datos.get("dias"),
            "saldo": str(a.datos.get("saldo", "")),
            "elevada_por": a.datos.get("elevada_por", []),
        }
        for a in resultado.alertas
    ]

    clientes = {
        nit: {
            "nombre": p.cliente_nombre,
            "cartera_total": str(p.cartera_total),
            "por_vencer": str(p.por_vencer),
            "vence_hoy": str(p.vence_hoy),
            "vencida": str(p.vencida),
            "pct_vencida": str(p.pct_vencida),
            "mayor_90": str(p.mayor_90),
            "pct_90": str(p.pct_90),
            "dias_max": p.dias_max,
            "n_vencidas": p.n_vencidas,
            "prioridad": p.prioridad.value,
            "prioridad_etiqueta": p.prioridad.etiqueta,
            "marcadores": list(p.marcadores),
        }
        for nit, p in resultado.indicadores["clientes"].items()
    }

    # Estado de cada factura, incluidas las que no generan alerta: es donde se
    # ve que un saldo negativo no es mora y que una saldada por credito sale.
    netos, _ = __import__(
        "busint_alertas.motores.cartera.creditos", fromlist=["aplicar_creditos"]
    ).aplicar_creditos(movimientos())
    # Solo lo que cambia con el corte: el saldo y el credito aplicado son los
    # mismos en todos los escenarios, asi que viajan una vez en `facturas_base`.
    facturas = []
    for m in sorted(netos, key=lambda x: x.orden_antiguedad):
        dias = m.dias_vencimiento(corte)
        bucket = config.buckets.asignar(dias) if m.saldo > 0 else None
        facturas.append({
            "f": m.factura, "d": dias,
            "b": bucket.codigo if bucket else None,
            "a": sorted(a["codigo"] for a in alertas if a["factura"] == m.factura),
        })

    return {
        "corte": corte.isoformat(),
        "globales": {k: str(v) for k, v in globales.items()
                     if k not in ("por_bucket", "facturas_por_bucket")},
        "por_bucket": {k: str(v) for k, v in globales["por_bucket"].items()},
        "facturas_por_bucket": globales["facturas_por_bucket"],
        "facturas": facturas,
        "alertas": alertas,
        "clientes": clientes,
        "marcadores": [
            {"codigo": m.codigo, "etiqueta": m.etiqueta, "cliente": m.sujeto,
             "explicacion": str(m.explicacion) if m.explicacion else ""}
            for m in resultado.marcadores
        ],
        "reglas_inactivas": dict(resultado.reglas_inactivas),
    }


def main() -> int:
    escenarios = {
        preset["id"]: [evaluar(corte, preset) for corte in CORTES]
        for preset in PRESETS
    }

    datos = {
        "generado_por": "motor real (busint_alertas), no una reimplementacion",
        "empresa": EMPRESA,
        "cortes": [c.isoformat() for c in CORTES],
        "buckets": [
            {"codigo": b.codigo, "etiqueta": b.etiqueta, "color": b.color,
             "desde": b.desde, "hasta": b.hasta, "alerta": b.alerta,
             "prioridad": b.prioridad_base.value, "accion": b.accion}
            for b in BUCKETS_BUSINT
        ],
        "reglas": [
            {"codigo": r.codigo, "etiqueta": r.etiqueta, "ambito": r.ambito,
             "alerta": r.alerta, "marcador": r.marcador,
             "eleva_prioridad": r.eleva_prioridad,
             "parametros": list(r.parametros_requeridos),
             "prioridad": r.prioridad.value, "accion": r.accion}
            for r in REGLAS
        ],
        "presets": [
            {"id": p["id"], "nombre": p["nombre"], "detalle": p["detalle"],
             "parametros": {k: str(v) for k, v in p["parametros"].items()}}
            for p in PRESETS
        ],
        "clientes": NOMBRES,
        "facturas_base": [
            {
                "factura": m.factura, "cliente": m.cliente_nit,
                "saldo": str(m.saldo), "saldo_bruto": str(m.saldo_bruto or m.saldo),
                "credito_aplicado": str(m.credito_aplicado),
                "vencimiento": m.fecha_vencimiento.isoformat(),
                "deudor": m.saldo > 0,
                "sin_bucket": (
                    "Crédito a favor" if m.saldo < 0
                    else ("Saldada por crédito" if m.saldo == 0 else None)
                ),
            }
            for m in sorted(
                __import__(
                    "busint_alertas.motores.cartera.creditos",
                    fromlist=["aplicar_creditos"],
                ).aplicar_creditos(movimientos())[0],
                key=lambda x: x.orden_antiguedad,
            )
        ],
        "gestiones": [
            {"cliente": nit, "factura": fac, "fecha": f.isoformat()}
            for (nit, fac), f in GESTIONES.items()
        ],
        "escenarios": escenarios,
    }

    DESTINO.parent.mkdir(exist_ok=True)
    DESTINO.write_text(
        json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    total = sum(len(v) for v in escenarios.values())
    print(
        f"{DESTINO.relative_to(RAIZ)}: {total} escenarios "
        f"({len(PRESETS)} configuraciones x {len(CORTES)} cortes), "
        f"{DESTINO.stat().st_size // 1024} kB."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
