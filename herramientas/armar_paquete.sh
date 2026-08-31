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

# Las capturas se agrupan en capturas/. Lo que NO entra en el paquete se
# declara en .gitattributes con export-ignore, no a base de borrados aqui:
# un borrado que se olvida no se nota hasta que alguien abre el paquete.
mkdir -p "$TEMPORAL/$NOMBRE/capturas"
for imagen in final_panel gestion lista app streamlit; do
    [[ -f "$imagen.png" ]] && cp "$imagen.png" "$TEMPORAL/$NOMBRE/capturas/"
done

# EMPIEZA-AQUI.txt viaja versionado en el repositorio, no se genera aqui: si
# se generara, cambiarlo exigiria editar un guion de empaquetado.
if [[ ! -f "$TEMPORAL/$NOMBRE/EMPIEZA-AQUI.txt" ]]; then
    echo "Falta EMPIEZA-AQUI.txt en el paquete." >&2
    exit 1
fi

tar -czf "$DESTINO" -C "$TEMPORAL" "$NOMBRE"
echo "$DESTINO ($(du -h "$DESTINO" | cut -f1))"
