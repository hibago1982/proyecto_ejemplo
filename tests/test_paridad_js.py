"""El port a JavaScript tiene que coincidir con el motor Python.

El banco de pruebas necesita evaluar en el navegador, y la politica de seguridad
de la pagina publicada impide correr Python alli. La consecuencia es una segunda
implementacion de las reglas, que es justo lo que §16 prohibe.

Esta prueba es lo que evita que esa copia mienta: genera escenarios aleatorios
pero reproducibles, los evalua con los dos motores y compara alerta por alerta y
cifra por cifra. Si divergen, la suite falla y el banco de pruebas deja de ser
publicable hasta arreglarlo.

Si `node` no esta disponible la prueba se salta, pero entonces nadie ha
verificado la paridad: no la trates como un aprobado.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from busint_alertas.core.motor import ContextoEjecucion
from busint_alertas.core.tipos import FASE_VIGENTE
from busint_alertas.motores.cartera import (
    ConfiguracionCartera, Movimiento, MotorCartera,
)
from busint_alertas.motores.cartera.historial import HistorialGestion

RAIZ = Path(__file__).resolve().parent.parent
MOTOR_JS = RAIZ / "banco_pruebas" / "motor.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node no esta instalado"
)

#: Rejilla de umbrales. Cubre reglas activas, inactivas y los bordes de cada una.
UMBRALES = [
    {"dias_preventivos": 15, "n_facturas_vencidas": 3, "pct_mayor_90_umbral": "40"},
    {"dias_preventivos": 7, "n_facturas_vencidas": 2, "pct_mayor_90_umbral": "25",
     "umbral_saldo_alto": "3000000", "umbral_saldo_critico": "9000000"},
    {"dias_preventivos": 30, "n_facturas_vencidas": 5, "pct_mayor_90_umbral": "60",
     "umbral_saldo_alto": "500000", "umbral_saldo_critico": "1000000",
     "dias_sin_gestion": 30},
    {"dias_preventivos": 1, "n_facturas_vencidas": 1, "pct_mayor_90_umbral": "0.01",
     "umbral_saldo_alto": "1", "umbral_saldo_critico": "1", "dias_sin_gestion": 1},
]


def cartera(semilla: int) -> list[dict]:
    """Cartera aleatoria pero reproducible.

    Los dias se eligen alrededor de los limites de bucket (0, 30, 60, 90, 120,
    150) porque ahi es donde una diferencia de redondeo o de operador cambia el
    resultado; en mitad de un rango casi cualquier implementacion coincide.
    """
    r = random.Random(semilla)
    bordes = [-31, -30, -16, -15, -1, 0, 1, 30, 31, 60, 61, 90, 91, 120, 121, 150, 151, 400]
    filas = []
    for i in range(r.randint(4, 12)):
        nit = r.choice(["900111", "900222", "900333"])
        dias = r.choice(bordes) + r.choice([-1, 0, 0, 1])
        saldo = r.choice(["0.01", "850000", "1000000.55", "3000000", "8600000",
                          "12400000.99", "26500000", "-900000", "0"])
        filas.append({
            "factura": f"F-{semilla}-{i}",
            "cliente": nit,
            "nombre": f"Cliente {nit}",
            "dias": dias,
            "saldo": saldo,
            "credito": r.choice(["0", "0", "0", "500000", "2500000", "99000000"]),
        })
    return filas


CORTE = date(2026, 8, 21)


def a_movimientos(filas: list[dict]) -> list[Movimiento]:
    movimientos = []
    for f in filas:
        vence = CORTE - timedelta(days=f["dias"])
        movimientos.append(Movimiento(
            empresa_id="E01", cliente_nit=f["cliente"], factura=f["factura"],
            fecha_emision=vence - timedelta(days=30), fecha_vencimiento=vence,
            saldo=Decimal(f["saldo"]), valor_credito=Decimal(f["credito"]),
            cliente_nombre=f["nombre"],
        ))
    return movimientos


def evaluar_python(filas: list[dict], umbrales: dict, gestion: date | None) -> dict:
    parametros = {
        k: (Decimal(v) if isinstance(v, str) else v) for k, v in umbrales.items()
    }
    config = ConfiguracionCartera.plantilla("E01", **parametros)
    movimientos = a_movimientos(filas)
    historial = HistorialGestion(
        ultima_gestion={},
        alerta_desde={(m.cliente_nit, m.factura): gestion for m in movimientos}
        if gestion else {},
    )
    r = MotorCartera().evaluar(
        ContextoEjecucion("E01", CORTE, config, fase_vigente=FASE_VIGENTE,
                          historial=historial),
        movimientos,
    )
    g = r.indicadores["globales"]
    return {
        "cartera_total": str(g["cartera_total"]),
        "por_vencer": str(g["por_vencer"]),
        "vence_hoy": str(g["vence_hoy"]),
        "vencida": str(g["vencida"]),
        "mayor_90": str(g["mayor_90"]),
        "pct_90": str(g["pct_90"]),
        "por_bucket": {k: str(v) for k, v in g["por_bucket"].items()},
        "alertas": sorted(
            f"{a.codigo}|{a.sujeto}|{a.entidad or ''}" for a in r.alertas
        ),
        "marcadores": sorted(f"{m.codigo}|{m.sujeto}" for m in r.marcadores),
        "prioridades": {
            nit: p.prioridad.value for nit, p in r.indicadores["clientes"].items()
        },
        "inactivas": sorted(r.reglas_inactivas),
    }


def evaluar_js(filas: list[dict], umbrales: dict, gestion: date | None) -> dict:
    entrada = {
        "corte": CORTE.isoformat(),
        "movimientos": [
            {
                "factura": f["factura"], "cliente": f["cliente"], "nombre": f["nombre"],
                "vencimiento": (CORTE - timedelta(days=f["dias"])).isoformat(),
                "emision": (CORTE - timedelta(days=f["dias"] + 30)).isoformat(),
                "saldo": f["saldo"], "credito": f["credito"],
            }
            for f in filas
        ],
        "parametros": umbrales,
        "gestiones": (
            {f'{f["cliente"]}|{f["factura"]}': gestion.isoformat() for f in filas}
            if gestion else {}
        ),
    }
    guion = f"""
import {{ evaluar, deCentavos, dePorcentaje }} from {json.dumps(str(MOTOR_JS))};
const e = {json.dumps(entrada)};
const r = evaluar(e);
const g = r.globales;
console.log(JSON.stringify({{
  cartera_total: deCentavos(g.carteraTotal),
  por_vencer: deCentavos(g.porVencer),
  vence_hoy: deCentavos(g.venceHoy),
  vencida: deCentavos(g.vencida),
  mayor_90: deCentavos(g.mayor90),
  pct_90: dePorcentaje(g.pct90),
  por_bucket: Object.fromEntries(Object.entries(r.porBucket).map(([k, v]) => [k, deCentavos(v)])),
  alertas: r.alertas.map(a => `${{a.codigo}}|${{a.cliente}}|${{a.factura ?? ""}}`).sort(),
  marcadores: r.marcadores.map(m => `${{m.codigo}}|${{m.cliente}}`).sort(),
  prioridades: Object.fromEntries(r.clientes.map(c => [c.nit, c.prioridad])),
  inactivas: Object.keys(r.reglasInactivas).sort(),
}}));
"""
    salida = subprocess.run(
        ["node", "--input-type=module", "-e", guion],
        capture_output=True, text=True, timeout=60,
    )
    if salida.returncode != 0:
        raise AssertionError(f"El motor JS fallo:\n{salida.stderr}")
    return json.loads(salida.stdout)


@pytest.mark.parametrize("semilla", range(24))
@pytest.mark.parametrize("iu", range(len(UMBRALES)))
def test_los_dos_motores_dan_lo_mismo(semilla, iu):
    filas = cartera(semilla)
    umbrales = UMBRALES[iu]
    gestion = date(2026, 6, 1) if "dias_sin_gestion" in umbrales else None

    esperado = evaluar_python(filas, umbrales, gestion)
    obtenido = evaluar_js(filas, umbrales, gestion)

    for campo in esperado:
        assert obtenido[campo] == esperado[campo], (
            f"Divergencia en '{campo}' (semilla {semilla}, umbrales {iu}).\n"
            f"  Python: {esperado[campo]}\n  JS:     {obtenido[campo]}"
        )
