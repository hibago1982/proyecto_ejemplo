"""Consultas de lectura que alimentan las pantallas.

Regla de oro de §4.2: el resultado se persiste, no se recalcula al vuelo en
cada consulta. Aqui no hay logica de negocio; solo se lee lo que el motor ya
dejo escrito y se le da la forma que pide cada pantalla.

Una sutileza sobre el grafico de aging: no puede salir de `ar_alerta`, porque
B00 "por vencer" no emite alerta y sus saldos no estarian ahi. Sale de
`ar_snapshot`, que guarda los totales de todos los buckets. Es un uso del
snapshot que va mas alla de C-16 y que conviene no perder al refactorizar.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from ..core.dinero import monto, porcentaje
from ..core.tipos import Prioridad
from ..persistencia import modelo
from ..persistencia.modelo import SIN_FACTURA

CERO = Decimal("0.00")


def ultimo_corte(sesion: Session, empresa_id: str) -> date | None:
    return sesion.scalar(
        select(func.max(modelo.Snapshot.corte)).where(
            modelo.Snapshot.empresa_id == empresa_id
        )
    )


def cortes(sesion: Session, empresa_id: str, limite: int = 24) -> list[dict]:
    """Cortes disponibles, del mas reciente. Alimenta el selector de fecha."""
    filas = sesion.execute(
        select(
            modelo.Snapshot.corte,
            func.max(modelo.Snapshot.generado),
            func.min(modelo.Snapshot.version_parametros),
            func.sum(modelo.Snapshot.cartera_total),
            func.count(modelo.Snapshot.id),
        )
        .where(modelo.Snapshot.empresa_id == empresa_id)
        .group_by(modelo.Snapshot.corte)
        .order_by(modelo.Snapshot.corte.desc())
        .limit(limite)
    ).all()
    return [
        {
            "corte": c,
            "generado": g,
            "version_parametros": v,
            "cartera_total": monto(total or 0),
            "n_clientes": n,
        }
        for c, g, v, total, n in filas
    ]


def riesgo(
    sesion: Session, empresa_id: str, corte: date
) -> Sequence[modelo.RiesgoCliente]:
    return list(
        sesion.scalars(
            select(modelo.RiesgoCliente)
            .where(
                modelo.RiesgoCliente.empresa_id == empresa_id,
                modelo.RiesgoCliente.corte == corte,
            )
            .order_by(
                modelo.RiesgoCliente.prioridad.desc(),
                modelo.RiesgoCliente.vencida.desc(),
            )
        )
    )


def totales_por_bucket(
    sesion: Session, empresa_id: str, corte: date
) -> dict[str, Decimal]:
    """Suma los totales por bucket de todos los clientes del corte."""
    acumulado: dict[str, Decimal] = {}
    for fila in sesion.scalars(
        select(modelo.Snapshot).where(
            modelo.Snapshot.empresa_id == empresa_id,
            modelo.Snapshot.corte == corte,
        )
    ):
        for codigo, valor in (fila.totales_por_bucket or {}).items():
            acumulado[codigo] = monto(acumulado.get(codigo, CERO) + Decimal(valor))
    return acumulado


def facturas_por_bucket(
    sesion: Session, empresa_id: str, corte: date
) -> dict[str, int]:
    """Conteo de facturas por bucket, tomado de las alertas del corte.

    Solo cuenta buckets que emiten alerta; B00 queda en cero porque una factura
    por vencer sin alerta preventiva no deja rastro en `ar_alerta`.
    """
    filas = sesion.execute(
        select(modelo.Alerta.bucket, func.count(func.distinct(modelo.Alerta.factura)))
        .where(
            modelo.Alerta.empresa_id == empresa_id,
            modelo.Alerta.corte == corte,
            modelo.Alerta.bucket.is_not(None),
            modelo.Alerta.factura != SIN_FACTURA,
        )
        .group_by(modelo.Alerta.bucket)
    ).all()
    return {b: n for b, n in filas}


def nombres_de_clientes(
    sesion: Session, empresa_id: str, corte: date
) -> dict[str, str]:
    """Nombres por NIT para un corte.

    Se trae el mapa completo de una vez en lugar de consultar por fila: son
    tantas filas como clientes, no como alertas, y evita el problema de las
    N+1 consultas en la pantalla mas usada del modulo.
    """
    filas = sesion.execute(
        select(modelo.RiesgoCliente.cliente_nit, modelo.RiesgoCliente.cliente_nombre)
        .where(
            modelo.RiesgoCliente.empresa_id == empresa_id,
            modelo.RiesgoCliente.corte == corte,
        )
    ).all()
    return {nit: nombre or "" for nit, nombre in filas}


def buckets_configurados(
    sesion: Session, empresa_id: str
) -> Sequence[modelo.AgingParam]:
    return list(
        sesion.scalars(
            select(modelo.AgingParam)
            .where(modelo.AgingParam.empresa_id == empresa_id)
            .order_by(modelo.AgingParam.orden)
        )
    )


def _base_alertas(empresa_id: str, corte: date) -> Select:
    return select(modelo.Alerta).where(
        modelo.Alerta.empresa_id == empresa_id, modelo.Alerta.corte == corte
    )


def lista_gestion(
    sesion: Session,
    empresa_id: str,
    corte: date,
    prioridad_minima: int | None = None,
    bucket: str | None = None,
    vendedor: str | None = None,
    zona: str | None = None,
    estado: str | None = "activa",
    busqueda: str | None = None,
    orden: str = "prioridad",
    pagina: int = 1,
    por_pagina: int = 50,
) -> tuple[int, Sequence[modelo.Alerta]]:
    """Bandeja de trabajo con los filtros y ordenamientos de §8.2."""
    consulta = _base_alertas(empresa_id, corte)

    if estado:
        consulta = consulta.where(modelo.Alerta.estado == estado)
    if prioridad_minima is not None:
        consulta = consulta.where(modelo.Alerta.prioridad >= prioridad_minima)
    if bucket:
        consulta = consulta.where(modelo.Alerta.bucket == bucket)
    if busqueda:
        patron = f"%{busqueda.strip()}%"
        consulta = consulta.where(
            or_(
                modelo.Alerta.cliente_nit.like(patron),
                modelo.Alerta.factura.like(patron),
            )
        )

    # Vendedor y zona viven en el JSON de datos porque no son del dominio de la
    # alerta sino de la factura que la origino. Se filtran en memoria mientras
    # no haya volumen que lo justifique; con volumen, columnas propias.
    filas = list(sesion.scalars(consulta))
    if vendedor:
        filas = [f for f in filas if (f.datos or {}).get("vendedor") == vendedor]
    if zona:
        filas = [f for f in filas if (f.datos or {}).get("zona") == zona]

    filas.sort(key=_clave_de_orden(orden))
    total = len(filas)
    desde = max(pagina - 1, 0) * por_pagina
    return total, filas[desde : desde + por_pagina]


def _clave_de_orden(orden: str):
    """§8.2: ordenable por prioridad, dias, saldo y cliente."""
    def por_prioridad(a: modelo.Alerta):
        return (-a.prioridad, -(a.dias or 0), a.cliente_nit)

    def por_dias(a: modelo.Alerta):
        return (-(a.dias or 0), -a.prioridad)

    def por_saldo(a: modelo.Alerta):
        return (-(a.saldo or CERO), -a.prioridad)

    def por_cliente(a: modelo.Alerta):
        return (a.cliente_nit, a.factura)

    return {
        "prioridad": por_prioridad,
        "dias": por_dias,
        "saldo": por_saldo,
        "cliente": por_cliente,
    }.get(orden, por_prioridad)


def alertas_de_cliente(
    sesion: Session, empresa_id: str, corte: date, cliente_nit: str
) -> Sequence[modelo.Alerta]:
    return list(
        sesion.scalars(
            _base_alertas(empresa_id, corte)
            .where(modelo.Alerta.cliente_nit == cliente_nit)
            .order_by(modelo.Alerta.prioridad.desc(), modelo.Alerta.factura)
        )
    )


def perfil_de_cliente(
    sesion: Session, empresa_id: str, corte: date, cliente_nit: str
) -> modelo.RiesgoCliente | None:
    return sesion.scalar(
        select(modelo.RiesgoCliente).where(
            modelo.RiesgoCliente.empresa_id == empresa_id,
            modelo.RiesgoCliente.corte == corte,
            modelo.RiesgoCliente.cliente_nit == cliente_nit,
        )
    )


def auditoria(
    sesion: Session, empresa_id: str, limite: int = 100
) -> Sequence[modelo.AuditoriaConfig]:
    return list(
        sesion.scalars(
            select(modelo.AuditoriaConfig)
            .where(modelo.AuditoriaConfig.empresa_id == empresa_id)
            .order_by(modelo.AuditoriaConfig.fecha_hora.desc())
            .limit(limite)
        )
    )


def ejecuciones(
    sesion: Session, empresa_id: str, limite: int = 20
) -> Sequence[modelo.Ejecucion]:
    return list(
        sesion.scalars(
            select(modelo.Ejecucion)
            .where(modelo.Ejecucion.empresa_id == empresa_id)
            .order_by(modelo.Ejecucion.inicio.desc())
            .limit(limite)
        )
    )


def etiqueta_prioridad(valor: int) -> str:
    return Prioridad(valor).etiqueta


def pct(parte: Decimal, total: Decimal) -> Decimal:
    return porcentaje(parte, total)
