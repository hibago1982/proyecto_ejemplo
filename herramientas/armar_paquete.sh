#!/usr/bin/env bash
# Arma el paquete de despliegue.
#
#   bash herramientas/armar_paquete.sh
#
# El .tar.gz no se versiona: sale del propio repositorio y quedaria obsoleto en
# cuanto cambie cualquier archivo. Este guion lo reconstruye desde el ultimo
# commit, asi que lo que se entrega es siempre codigo confirmado y nunca un
# arbol de trabajo a medio editar.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NOMBRE="busint-motor-alertas"
DESTINO="$RAIZ/$NOMBRE.tar.gz"
TEMPORAL="$(mktemp -d)"
trap 'rm -rf "$TEMPORAL"' EXIT

cd "$RAIZ"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "Aviso: hay cambios sin confirmar. El paquete sale del ultimo commit." >&2
fi

mkdir -p "$TEMPORAL/$NOMBRE"
git archive --format=tar HEAD | tar -x -C "$TEMPORAL/$NOMBRE"

# El panel ya construido viaja dentro, para que montarlo no exija instalar Node.
if [[ ! -d frontend/dist ]]; then
    echo "Falta frontend/dist. Construyelo con: cd frontend && npm ci && npm run build" >&2
    exit 1
fi
mkdir -p "$TEMPORAL/$NOMBRE/frontend/dist"
cp -r frontend/dist/. "$TEMPORAL/$NOMBRE/frontend/dist/"

# Las capturas se agrupan aparte para no dejarlas sueltas en la raiz.
mkdir -p "$TEMPORAL/$NOMBRE/capturas"
for imagen in final_panel gestion lista app streamlit; do
    [[ -f "$imagen.png" ]] && cp "$imagen.png" "$TEMPORAL/$NOMBRE/capturas/"
done
rm -f "$TEMPORAL/$NOMBRE"/*.png

tar -czf "$DESTINO" -C "$TEMPORAL" "$NOMBRE"
echo "$DESTINO ($(du -h "$DESTINO" | cut -f1))"
