#!/usr/bin/env python3
"""Inserta los datos del motor dentro de la pagina del banco de pruebas.

Se mantiene separado del generador para poder retocar la plantilla sin volver a
correr el motor sobre los 96 escenarios.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "banco_pruebas"


def main() -> int:
    datos = (BANCO / "datos.json").read_text(encoding="utf-8")
    # El JSON viaja dentro de un <script type="application/json">: lo unico que
    # hay que neutralizar es un "</script>" literal que cerraria la etiqueta.
    datos = datos.replace("</", "<\\/")

    salida = BANCO / "index.html"
    salida.write_text(
        (BANCO / "plantilla.html").read_text(encoding="utf-8").replace("__DATOS__", datos),
        encoding="utf-8",
    )
    print(f"{salida.relative_to(RAIZ)}: {salida.stat().st_size // 1024} kB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
