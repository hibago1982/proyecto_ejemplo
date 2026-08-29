"""El contrato versionado tiene que seguir al codigo.

Sin esta prueba, `contrato/openapi.json` se queda atras en silencio y el
frontend genera tipos que ya no corresponden al backend, que es exactamente el
fallo silencioso que TypeScript deberia evitar.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

RAIZ = Path(__file__).resolve().parent.parent.parent
CONTRATO = RAIZ / "contrato" / "openapi.json"


@pytest.fixture(scope="module")
def generado():
    import sys

    sys.path.insert(0, str(RAIZ / "herramientas"))
    from generar_contrato import generar

    return generar()


def test_el_contrato_versionado_esta_al_dia(generado):
    assert CONTRATO.exists(), (
        "Falta contrato/openapi.json. Genera con: "
        "python herramientas/generar_contrato.py"
    )
    guardado = json.loads(CONTRATO.read_text(encoding="utf-8"))
    assert guardado == generado, (
        "El contrato versionado no coincide con el codigo. "
        "Ejecuta: python herramientas/generar_contrato.py"
    )


def test_todo_endpoint_tiene_resumen(generado):
    """Un resumen vacio se convierte en un nombre de funcion sin sentido
    en el cliente generado."""
    sin_resumen = [
        f"{metodo.upper()} {ruta}"
        for ruta, ops in generado["paths"].items()
        for metodo, op in ops.items()
        if not op.get("summary")
    ]
    assert sin_resumen == []


def test_los_montos_nunca_viajan_como_numero(generado):
    """C-09 de extremo a extremo: si un monto se declara number, el frontend
    lo lee como float y pierde los centavos."""
    esquemas = generado["components"]["schemas"]
    sospechosos = []
    for nombre, esquema in esquemas.items():
        for campo, definicion in (esquema.get("properties") or {}).items():
            if campo in {
                "saldo", "saldo_bruto", "credito_aplicado", "cartera_total",
                "vencida", "por_vencer", "vence_hoy", "mayor_90", "mayor_150",
                "valor", "pct_vencida", "pct_90", "pct_sobre_total",
            }:
                tipos = {definicion.get("type")} | {
                    v.get("type") for v in definicion.get("anyOf", [])
                }
                if "number" in tipos:
                    sospechosos.append(f"{nombre}.{campo}")
    assert sospechosos == []
