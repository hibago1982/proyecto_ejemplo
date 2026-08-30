"""Exportacion a PDF y Excel (§9).

Ambas leen del mismo resultado persistido que la pantalla. §13 lo exige como
criterio de aceptacion: "El PDF y Excel muestran exactamente la misma
clasificacion que la pantalla para el mismo corte".
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from ...salidas import cargar, excel, pdf
from ..dependencias import CorteResuelto, Empresa, SesionBD

router = APIRouter(tags=["exportar"])


def _corte(sesion, empresa_id, corte):
    try:
        return cargar(sesion, empresa_id, corte)
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from None


@router.get(
    "/exportar/excel",
    summary="Excel del corte",
    response_class=Response,
    responses={200: {"content": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
    }}},
)
def a_excel(sesion: SesionBD, empresa_id: Empresa, corte: CorteResuelto) -> Response:
    datos = _corte(sesion, empresa_id, corte)
    nombre = f"cartera_{empresa_id}_{corte:%Y%m%d}.xlsx"
    return Response(
        content=excel.generar(datos),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get(
    "/exportar/pdf",
    summary="PDF del corte",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def a_pdf(sesion: SesionBD, empresa_id: Empresa, corte: CorteResuelto) -> Response:
    datos = _corte(sesion, empresa_id, corte)
    nombre = f"cartera_{empresa_id}_{corte:%Y%m%d}.pdf"
    return Response(
        content=pdf.generar(datos),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nombre}"'},
    )
