#!/usr/bin/env python3
"""Arma la pagina del banco de pruebas.

Inserta el motor portado a JavaScript y la cartera de ejemplo dentro de la
plantilla, quitando las palabras `export` porque el guion va incrustado en la
pagina y no se importa como modulo.

    python herramientas/armar_banco_pruebas.py
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco_pruebas"


def sin_exports(fuente: str) -> str:
    return re.sub(r"^export ", "", fuente, flags=re.MULTILINE)


def main() -> int:
    plantilla = (BANCO / "plantilla.html").read_text(encoding="utf-8")
    pagina = (
        plantilla
        .replace("__MOTOR__", sin_exports((BANCO / "motor.js").read_text(encoding="utf-8")))
        .replace("__CARTERA__", sin_exports(
            (BANCO / "cartera_ejemplo.js").read_text(encoding="utf-8")))
    )

    salida = BANCO / "index.html"
    salida.write_text(pagina, encoding="utf-8")
    print(f"{salida.relative_to(RAIZ)}: {salida.stat().st_size // 1024} kB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
