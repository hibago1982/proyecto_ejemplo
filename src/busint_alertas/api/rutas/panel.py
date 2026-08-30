"""Panel de control (§8.1) y lista de cortes.

El objetivo declarado es responder en cinco segundos: como esta la cartera y a
quien llamo hoy. Por eso el panel entero viaja en una sola respuesta y no en
cuatro llamadas que el frontend tendria que coordinar.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from ...core.tipos import FASE_VIGENTE, Prioridad
from ...motores.cartera.reglas import REGLAS
from ...persistencia import configuracion as config_bd
from .. import consultas
from ..dependencias import CorteResuelto, Empresa, SesionBD
from ..esquemas import BarraAging, ClienteEnRanking, Corte, Panel, TarjetaKPI

router = APIRouter(tags=["panel"])
CERO = Decimal("0.00")


@router.get("/cortes", response_model=list[Corte], summary="Cortes disponibles")
def listar_cortes(sesion: SesionBD, empresa_id: Empresa) -> list[Corte]:
    return [Corte(**c) for c in consultas.cortes(sesion, empresa_id)]


@router.get("/panel", response_model=Panel, summary="Panel de control")
def panel(sesion: SesionBD, empresa_id: Empresa, corte: CorteResuelto) -> Panel:
    perfiles = consultas.riesgo(sesion, empresa_id, corte)
    por_bucket = consultas.totales_por_bucket(sesion, empresa_id, corte)
    conteos = consultas.facturas_por_bucket(sesion, empresa_id, corte)
    buckets = consultas.buckets_configurados(sesion, empresa_id)

    total = sum((p.cartera_total for p in perfiles), CERO)
    criticos = [p for p in perfiles if p.prioridad >= Prioridad.MUY_ALTA.value]

    kpis = [
        _kpi("cartera_total", "Cartera total", total, total),
        _kpi("por_vencer", "Por vencer",
             sum((p.por_vencer for p in perfiles), CERO), total),
        # C-14: "vence hoy" es indicador propio. Sin el, los tres no suman el total.
        _kpi("vence_hoy", "Vence hoy",
             sum((p.vence_hoy for p in perfiles), CERO), total),
        _kpi("vencida", "Vencida",
             sum((p.vencida for p in perfiles), CERO), total),
        _kpi("mayor_90", "Mas de 90 dias",
             sum((p.mayor_90 for p in perfiles), CERO), total),
    ]

    aging = [
        BarraAging(
            bucket=b.codigo, etiqueta=b.etiqueta, color=b.color,
            saldo=por_bucket.get(b.codigo, CERO),
            facturas=conteos.get(b.codigo, 0),
            pct_sobre_total=consultas.pct(por_bucket.get(b.codigo, CERO), total),
        )
        for b in buckets
    ]

    ranking = [
        ClienteEnRanking(
            cliente_nit=p.cliente_nit, cliente_nombre=p.cliente_nombre,
            cartera_total=p.cartera_total, vencida=p.vencida,
            pct_vencida=p.pct_vencida, pct_90=p.pct_90, dias_max=p.dias_max,
            n_vencidas=p.n_vencidas, prioridad=p.prioridad,
            prioridad_etiqueta=consultas.etiqueta_prioridad(p.prioridad),
            marcadores=list(p.marcadores or []),
        )
        for p in perfiles[:20]
    ]

    detalle = consultas.cortes(sesion, empresa_id, limite=1)
    cabecera = next((c for c in detalle if c["corte"] == corte), None)

    return Panel(
        empresa_id=empresa_id, corte=corte,
        generado=cabecera["generado"] if cabecera else None,
        version_parametros=cabecera["version_parametros"] if cabecera else None,
        kpis=kpis, aging=aging, ranking=ranking,
        n_clientes=len(perfiles),
        n_facturas=sum(conteos.values()),
        reglas_inactivas=_reglas_inactivas(sesion, empresa_id),
    )


def _reglas_inactivas(sesion, empresa_id: str) -> dict[str, str]:
    """Reglas que no se estan evaluando, y por que.

    Se deriva de la configuracion vigente en vez de guardarse en la corrida:
    asi hay una sola definicion de "regla inactiva", la de `inactiva_porque`,
    y el panel no puede contradecir a la pantalla de configuracion.
    """
    try:
        config = config_bd.cargar(sesion, empresa_id)
    except LookupError:
        return {}
    inactivas = {}
    for regla in REGLAS:
        motivo = regla.inactiva_porque(config.parametros, FASE_VIGENTE)
        if motivo is not None:
            inactivas[regla.codigo] = motivo
    return inactivas


def _kpi(codigo: str, etiqueta: str, valor: Decimal, total: Decimal) -> TarjetaKPI:
    return TarjetaKPI(
        codigo=codigo, etiqueta=etiqueta, valor=valor,
        pct_sobre_total=consultas.pct(valor, total),
    )


@router.get(
    "/panel/criticos", response_model=list[ClienteEnRanking],
    summary="Clientes que requieren atencion",
)
def criticos(
    sesion: SesionBD, empresa_id: Empresa, corte: CorteResuelto, limite: int = 20
) -> list[ClienteEnRanking]:
    perfiles = consultas.riesgo(sesion, empresa_id, corte)
    return [
        ClienteEnRanking(
            cliente_nit=p.cliente_nit, cliente_nombre=p.cliente_nombre,
            cartera_total=p.cartera_total, vencida=p.vencida,
            pct_vencida=p.pct_vencida, pct_90=p.pct_90, dias_max=p.dias_max,
            n_vencidas=p.n_vencidas, prioridad=p.prioridad,
            prioridad_etiqueta=consultas.etiqueta_prioridad(p.prioridad),
            marcadores=list(p.marcadores or []),
        )
        for p in perfiles
        if p.prioridad >= Prioridad.MUY_ALTA.value
    ][:limite]
