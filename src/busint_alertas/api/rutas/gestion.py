"""Lista de gestion (§8.2) y detalle del cliente (§8.3).

§16 exige drill-down de indicador a cliente, a factura y a gestion. El detalle
del cliente devuelve sus alertas dentro de la misma respuesta para que abrir
una ficha sea una llamada y no dos.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from ...core.tipos import TipoGestion
from ...persistencia import gestion as gestion_bd
from .. import consultas
from ..dependencias import CorteResuelto, Empresa, SesionBD
from ..seguridad import Gestor
from ..esquemas import (
    DetalleCliente,
    FilaGestion,
    Gestion,
    ListaGestion,
    NuevaGestion,
)

router = APIRouter(tags=["gestion"])


def _a_fila(alerta, nombres: dict[str, str] | None = None) -> FilaGestion:
    datos = alerta.datos or {}
    return FilaGestion(
        id=alerta.id, cliente_nit=alerta.cliente_nit,
        cliente_nombre=(nombres or {}).get(alerta.cliente_nit, ""),
        factura=alerta.factura,
        codigo=alerta.codigo, etiqueta=alerta.etiqueta, bucket=alerta.bucket,
        dias=alerta.dias, saldo=alerta.saldo, saldo_bruto=alerta.saldo_bruto,
        credito_aplicado=alerta.credito_aplicado, prioridad=alerta.prioridad,
        prioridad_etiqueta=consultas.etiqueta_prioridad(alerta.prioridad),
        accion=alerta.accion, estado=alerta.estado,
        explicacion=alerta.explicacion,
        vendedor=datos.get("vendedor"), zona=datos.get("zona"),
    )


@router.get("/gestion", response_model=ListaGestion, summary="Lista de gestion")
def lista(
    sesion: SesionBD,
    empresa_id: Empresa,
    corte: CorteResuelto,
    prioridad_minima: Annotated[int | None, Query(ge=0, le=4)] = None,
    bucket: str | None = None,
    vendedor: str | None = None,
    zona: str | None = None,
    estado: str | None = "activa",
    busqueda: Annotated[str | None, Query(description="NIT o numero de factura")] = None,
    orden: Annotated[str, Query(pattern="^(prioridad|dias|saldo|cliente)$")] = "prioridad",
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=500)] = 50,
) -> ListaGestion:
    total, filas = consultas.lista_gestion(
        sesion, empresa_id, corte,
        prioridad_minima=prioridad_minima, bucket=bucket, vendedor=vendedor,
        zona=zona, estado=estado, busqueda=busqueda, orden=orden,
        pagina=pagina, por_pagina=por_pagina,
    )
    nombres = consultas.nombres_de_clientes(sesion, empresa_id, corte)
    return ListaGestion(
        corte=corte, total=total, pagina=pagina, por_pagina=por_pagina,
        filas=[_a_fila(f, nombres) for f in filas],
    )


@router.get(
    "/clientes/{cliente_nit}",
    response_model=DetalleCliente,
    summary="Detalle del cliente",
)
def detalle(
    sesion: SesionBD, empresa_id: Empresa, cliente_nit: str, corte: CorteResuelto
) -> DetalleCliente:
    perfil = consultas.perfil_de_cliente(sesion, empresa_id, corte, cliente_nit)
    if perfil is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"El cliente '{cliente_nit}' no tiene cartera en el corte {corte}.",
        )
    alertas = consultas.alertas_de_cliente(sesion, empresa_id, corte, cliente_nit)
    return DetalleCliente(
        cliente_nit=perfil.cliente_nit, cliente_nombre=perfil.cliente_nombre,
        corte=corte, cartera_total=perfil.cartera_total,
        por_vencer=perfil.por_vencer, vence_hoy=perfil.vence_hoy,
        vencida=perfil.vencida, pct_vencida=perfil.pct_vencida,
        mayor_90=perfil.mayor_90, pct_90=perfil.pct_90,
        mayor_150=perfil.mayor_150, dias_max=perfil.dias_max,
        n_facturas=perfil.n_facturas, n_vencidas=perfil.n_vencidas,
        prioridad=perfil.prioridad,
        prioridad_etiqueta=consultas.etiqueta_prioridad(perfil.prioridad),
        marcadores=list(perfil.marcadores or []),
        alertas=[_a_fila(a, {perfil.cliente_nit: perfil.cliente_nombre}) for a in alertas],
        gestiones=[
            Gestion.model_validate(g)
            for g in gestion_bd.historial_de(sesion, empresa_id, cliente_nit)
        ],
    )


@router.post(
    "/clientes/{cliente_nit}/gestiones",
    response_model=Gestion,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una gestion de cobranza",
)
def registrar_gestion(
    sesion: SesionBD,
    quien: Gestor,
    cliente_nit: str,
    peticion: NuevaGestion,
    corte: CorteResuelto,
) -> Gestion:
    """§11: el gestor registra la gestion y la alerta pasa a gestionada.

    No toca el saldo ni el bucket. §16 separa el estado de la gestion del de la
    factura: una factura sigue vencida aunque ya se haya gestionado.
    """
    try:
        tipo = TipoGestion(peticion.tipo)
    except ValueError:
        validos = ", ".join(t.value for t in TipoGestion)
        raise HTTPException(
            422, f"Tipo de gestion '{peticion.tipo}' no valido. Use: {validos}."
        ) from None

    try:
        fila = gestion_bd.registrar(
            sesion, quien.empresa_id, corte,
            gestion_bd.NuevaGestion(
                cliente_nit=cliente_nit,
                factura=peticion.factura,
                # El usuario sale del token y no del cuerpo: §10.3 exige saber
                # quien hizo cada gestion, y un dato que el cliente elige no
                # sirve como rastro.
                usuario_id=quien.usuario_id,
                tipo=tipo,
                resultado=peticion.resultado,
                observacion=peticion.observacion,
                compromiso_fecha=peticion.compromiso_fecha,
                compromiso_valor=peticion.compromiso_valor,
            ),
        )
    except gestion_bd.ErrorDeGestion as e:
        # 422 y no 404: la peticion esta bien formada pero no es aplicable.
        raise HTTPException(422, str(e)) from None
    return Gestion.model_validate(fila)


@router.get(
    "/clientes/{cliente_nit}/gestiones",
    response_model=list[Gestion],
    summary="Historial de gestiones del cliente",
)
def gestiones(
    sesion: SesionBD, empresa_id: Empresa, cliente_nit: str
) -> list[Gestion]:
    return [
        Gestion.model_validate(g)
        for g in gestion_bd.historial_de(sesion, empresa_id, cliente_nit)
    ]
