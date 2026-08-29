"""Registro de gestiones de cobranza y su efecto sobre las alertas (§11, §12).

Dos cosas que conviene no confundir, porque §16 las separa de forma expresa:

  * El estado de la **factura** lo determina el ERP y el paso del tiempo: una
    factura sigue vencida y sube de bucket aunque ya se haya gestionado.
  * El estado de la **alerta** lo determina la gestion: GESTIONADA significa
    que alguien la trabajo, no que el cliente haya pagado.

Por eso registrar una gestion no toca el saldo ni el bucket. Solo mueve la
alerta a GESTIONADA y deja la fecha, que es lo que A12 mira despues.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.tipos import EstadoAlerta, TipoGestion
from ..motores.cartera.historial import HistorialGestion
from . import modelo
from .modelo import SIN_FACTURA


@dataclass(frozen=True)
class NuevaGestion:
    """Lo que un gestor registra tras contactar al cliente (§11)."""

    cliente_nit: str
    factura: str
    usuario_id: str
    tipo: TipoGestion
    resultado: str | None = None
    observacion: str | None = None
    compromiso_fecha: date | None = None
    compromiso_valor: Decimal | None = None
    momento: datetime | None = None
    """Cuando ocurrio. Se pasa explicitamente para que las pruebas no dependan
    del reloj y para poder cargar gestiones historicas."""


class ErrorDeGestion(ValueError):
    """La gestion no puede registrarse tal como viene."""


def registrar(
    sesion: Session,
    empresa_id: str,
    corte: date,
    gestion: NuevaGestion,
) -> modelo.Gestion:
    """Guarda la gestion y marca como gestionadas las alertas de esa factura."""
    if gestion.compromiso_fecha is not None and gestion.compromiso_valor is None:
        raise ErrorDeGestion(
            "Un compromiso de pago necesita fecha y valor. Falta el valor."
        )
    if gestion.compromiso_valor is not None and gestion.compromiso_fecha is None:
        raise ErrorDeGestion(
            "Un compromiso de pago necesita fecha y valor. Falta la fecha."
        )
    if gestion.compromiso_valor is not None and gestion.compromiso_valor <= 0:
        raise ErrorDeGestion("El valor comprometido debe ser mayor que cero.")

    momento = gestion.momento or datetime.utcnow()

    alertas = list(
        sesion.scalars(
            select(modelo.Alerta).where(
                modelo.Alerta.empresa_id == empresa_id,
                modelo.Alerta.corte == corte,
                modelo.Alerta.cliente_nit == gestion.cliente_nit,
                modelo.Alerta.factura == (gestion.factura or SIN_FACTURA),
            )
        )
    )
    if not alertas:
        raise ErrorDeGestion(
            f"No hay alertas de la factura '{gestion.factura}' del cliente "
            f"'{gestion.cliente_nit}' en el corte {corte}."
        )

    fila = modelo.Gestion(
        empresa_id=empresa_id,
        alerta_id=alertas[0].id,
        cliente_nit=gestion.cliente_nit,
        factura=gestion.factura or SIN_FACTURA,
        fecha=momento,
        corte=corte,
        usuario_id=gestion.usuario_id,
        tipo=gestion.tipo.value,
        resultado=gestion.resultado,
        compromiso_fecha=gestion.compromiso_fecha,
        compromiso_valor=gestion.compromiso_valor,
        observacion=gestion.observacion,
    )
    sesion.add(fila)

    for alerta in alertas:
        # Una alerta ya cerrada por pago no vuelve a abrirse porque alguien
        # registre una llamada tardia.
        if EstadoAlerta(alerta.estado).esta_abierta:
            alerta.estado = EstadoAlerta.GESTIONADA.value

    sesion.flush()
    return fila


def historial_de(
    sesion: Session, empresa_id: str, cliente_nit: str, factura: str | None = None
) -> list[modelo.Gestion]:
    """Gestiones de un cliente, de la mas reciente a la mas antigua."""
    consulta = select(modelo.Gestion).where(
        modelo.Gestion.empresa_id == empresa_id,
        modelo.Gestion.cliente_nit == cliente_nit,
    )
    if factura is not None:
        consulta = consulta.where(modelo.Gestion.factura == factura)
    return list(sesion.scalars(consulta.order_by(modelo.Gestion.fecha.desc())))


def construir_historial(sesion: Session, empresa_id: str) -> HistorialGestion:
    """Arma el historial que el motor necesita para evaluar A12.

    Son dos consultas agregadas y no una por factura: la ultima gestion de cada
    factura y el primer corte de cada alerta. El motor las recibe ya resueltas,
    porque no consulta la base (§4.2).
    """
    ultima = {
        (nit, factura): fecha.date() if isinstance(fecha, datetime) else fecha
        for nit, factura, fecha in sesion.execute(
            select(
                modelo.Gestion.cliente_nit,
                modelo.Gestion.factura,
                func.max(modelo.Gestion.fecha),
            )
            .where(modelo.Gestion.empresa_id == empresa_id)
            .group_by(modelo.Gestion.cliente_nit, modelo.Gestion.factura)
        ).all()
    }

    desde = {
        (nit, factura): primer
        for nit, factura, primer in sesion.execute(
            select(
                modelo.Alerta.cliente_nit,
                modelo.Alerta.factura,
                func.min(modelo.Alerta.primer_corte),
            )
            .where(
                modelo.Alerta.empresa_id == empresa_id,
                modelo.Alerta.factura != SIN_FACTURA,
            )
            .group_by(modelo.Alerta.cliente_nit, modelo.Alerta.factura)
        ).all()
        if primer is not None
    }

    return HistorialGestion(ultima_gestion=ultima, alerta_desde=desde)
