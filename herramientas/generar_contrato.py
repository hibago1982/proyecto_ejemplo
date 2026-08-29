#!/usr/bin/env python3
"""Genera el contrato OpenAPI en `contrato/openapi.json`.

Es el entregable de la etapa 3: el contrato publicado, y la fuente de la que el
frontend genera sus tipos de TypeScript. Que este versionado en el repositorio
tiene un proposito concreto: un cambio incompatible en el API aparece como
diferencia en la revision de codigo, en vez de descubrirse cuando el frontend
falla delante del usuario.

    python herramientas/generar_contrato.py

Y del lado del frontend:

    npx openapi-typescript contrato/openapi.json -o src/api/tipos.ts
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from sqlalchemy.pool import StaticPool  # noqa: E402

from busint_alertas.api import crear_app  # noqa: E402
from busint_alertas.persistencia import (  # noqa: E402
    crear_engine, crear_esquema, fabrica_de_sesiones,
)

DESTINO = RAIZ / "contrato" / "openapi.json"


def generar() -> dict:
    """Construye la aplicacion solo para leerle el contrato.

    Se monta contra una base en memoria: generar el contrato no debe exigir
    tener PostgreSQL levantado ni tocar datos reales.
    """
    engine = crear_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    crear_esquema(engine)
    return crear_app(fabrica_de_sesiones(engine)).openapi()


def main() -> int:
    contrato = generar()
    DESTINO.parent.mkdir(exist_ok=True)
    nuevo = json.dumps(contrato, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    if DESTINO.exists() and DESTINO.read_text(encoding="utf-8") == nuevo:
        print(f"{DESTINO.relative_to(RAIZ)} ya estaba al dia.")
        return 0

    DESTINO.write_text(nuevo, encoding="utf-8")
    print(
        f"{DESTINO.relative_to(RAIZ)} actualizado: "
        f"{len(contrato['paths'])} rutas, "
        f"{len(contrato['components']['schemas'])} esquemas."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
