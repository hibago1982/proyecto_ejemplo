"""Esquema de persistencia del motor (etapa 2).

Sigue las entidades de §6.2 del documento de arquitectura, que a su vez corrige
las de §10 de la especificacion. El motor destino es PostgreSQL 16, pero los
modelos se mantienen portables para poder probarlos sobre SQLite: lo que si es
exclusivo de PostgreSQL (particionado de ar_snapshot, indices sobre JSONB,
seguridad a nivel de fila) vive en la migracion, no aqui.

Dos decisiones que conviene no perder de vista:

C-17. `ar_alerta` lleva una restriccion unica sobre
empresa + corte + cliente + factura + regla. La especificacion definia esa clave
como logica pero no obligaba a materializarla, y sin restriccion en la base una
segunda ejecucion del mismo corte inserta filas nuevas en vez de actualizar.

Sobre el campo `factura`. Las alertas de cliente (A10, A11) no cuelgan de
ninguna factura. Se guardan con cadena vacia y no con NULL porque en SQL dos
NULL no son iguales entre si: con NULL la restriccion unica dejaria pasar
duplicados justo en las alertas que mas se repiten.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

#: Marcador para la ausencia de factura en una alerta de cliente. Ver el modulo.
SIN_FACTURA = ""

DINERO = Numeric(18, 2)
PORCENTAJE = Numeric(7, 2)


class Base(DeclarativeBase):
    pass


class AgingParam(Base):
    """Buckets de antiguedad configurables por empresa (§5.2, §8.4).

    §16: los rangos nunca se escriben en el codigo. Esta tabla es la razon por
    la que `ConfiguracionCartera` puede construirse sin tocar el motor.
    """

    __tablename__ = "ar_aging_param"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uq_aging_empresa_codigo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[str] = mapped_column(String(32), index=True)
    codigo: Mapped[str] = mapped_column(String(8))
    etiqueta: Mapped[str] = mapped_column(String(64))
    desde: Mapped[int | None] = mapped_column(Integer)
    hasta: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str] = mapped_column(String(16))
    prioridad_base: Mapped[int] = mapped_column(Integer)
    accion: Mapped[str] = mapped_column(String(64))
    alerta: Mapped[str | None] = mapped_column(String(8))
    orden: Mapped[int] = mapped_column(Integer)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class AlertRule(Base):
    """Reglas R01-R06 y umbrales de A11 y A12 (§5.4).

    `parametros` es JSON y no una columna por umbral: cada regla lleva su
    parametro con nombre y forma propios, y anadir una regla nueva no debe
    obligar a migrar el esquema. En PostgreSQL la columna es JSONB e indexable.
    """

    __tablename__ = "ar_alert_rule"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uq_rule_empresa_codigo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[str] = mapped_column(String(32), index=True)
    codigo: Mapped[str] = mapped_column(String(8))
    tipo: Mapped[str] = mapped_column(String(16))
    parametros: Mapped[dict] = mapped_column(JSON, default=dict)
    prioridad: Mapped[int] = mapped_column(Integer)
    accion: Mapped[str] = mapped_column(String(64))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Alerta(Base):
    """Resultado de la evaluacion, por factura o por cliente (§10.2)."""

    __tablename__ = "ar_alerta"
    __table_args__ = (
        # C-17: la clave logica, ahora materializada. Sin esto el reproceso duplica.
        UniqueConstraint(
            "empresa_id", "corte", "cliente_nit", "factura", "regla",
            name="uq_alerta_clave_logica",
        ),
        # Alimenta el panel y la lista de gestion, que es la consulta caliente.
        Index("ix_alerta_panel", "empresa_id", "corte", "prioridad"),
        # Soporta el detalle del cliente y el drill-down.
        Index("ix_alerta_cliente", "empresa_id", "cliente_nit", "corte"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[str] = mapped_column(String(32))
    corte: Mapped[date] = mapped_column(Date)
    cliente_nit: Mapped[str] = mapped_column(String(32))
    factura: Mapped[str] = mapped_column(String(32), default=SIN_FACTURA)
    regla: Mapped[str] = mapped_column(String(8))

    codigo: Mapped[str] = mapped_column(String(8))
    etiqueta: Mapped[str] = mapped_column(String(64))
    prioridad: Mapped[int] = mapped_column(Integer)
    accion: Mapped[str] = mapped_column(String(64))
    estado: Mapped[str] = mapped_column(String(24), default="activa")

    bucket: Mapped[str | None] = mapped_column(String(8))
    dias: Mapped[int | None] = mapped_column(Integer)
    saldo: Mapped[Decimal | None] = mapped_column(DINERO)
    saldo_bruto: Mapped[Decimal | None] = mapped_column(DINERO)
    credito_aplicado: Mapped[Decimal | None] = mapped_column(DINERO)

    origen_dias: Mapped[str] = mapped_column(String(16), default="calculado")
    """Como se obtuvieron los dias. §5.1 admite el campo del ERP o el calculo."""

    explicacion: Mapped[str | None] = mapped_column(Text)
    """Cadena legible de por que se disparo. §7.4 y §10.3."""

    datos: Mapped[dict] = mapped_column(JSON, default=dict)
    detectado_pago: Mapped[date | None] = mapped_column(Date)
    """Fecha en que se detecto que la factura ya no estaba abierta (C-18)."""

    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RiesgoCliente(Base):
    """Estado agregado por cliente en un corte (§6)."""

    __tablename__ = "ar_riesgo_cliente"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "corte", "cliente_nit", name="uq_riesgo_clave"
        ),
        Index("ix_riesgo_ranking", "empresa_id", "corte", "prioridad"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[str] = mapped_column(String(32))
    corte: Mapped[date] = mapped_column(Date)
    cliente_nit: Mapped[str] = mapped_column(String(32))
    cliente_nombre: Mapped[str] = mapped_column(String(128), default="")

    cartera_total: Mapped[Decimal] = mapped_column(DINERO)
    por_vencer: Mapped[Decimal] = mapped_column(DINERO)
    vence_hoy: Mapped[Decimal] = mapped_column(DINERO)
    vencida: Mapped[Decimal] = mapped_column(DINERO)
    pct_vencida: Mapped[Decimal] = mapped_column(PORCENTAJE)
    mayor_90: Mapped[Decimal] = mapped_column(DINERO)
    pct_90: Mapped[Decimal] = mapped_column(PORCENTAJE)
    mayor_150: Mapped[Decimal] = mapped_column(DINERO)
    dias_max: Mapped[int] = mapped_column(Integer)
    n_facturas: Mapped[int] = mapped_column(Integer)
    n_vencidas: Mapped[int] = mapped_column(Integer)
    prioridad: Mapped[int] = mapped_column(Integer)

    marcadores: Mapped[list] = mapped_column(JSON, default=list)
    """Aloja R04 y R05, que son marcadores de riesgo y no alertas (C-04)."""


class Snapshot(Base):
    """Congelado del corte, para poder reproducirlo (C-16).

    Deja de ser opcional. §9 exige regenerar el PDF de una fecha de corte
    pasada, pero el ERP solo expone cuentas abiertas de hoy: una factura pagada
    ayer ya no aparece. Sin este congelado, un corte pasado es irrecuperable.
    """

    __tablename__ = "ar_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "corte", "cliente_nit", name="uq_snapshot_clave"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[str] = mapped_column(String(32))
    corte: Mapped[date] = mapped_column(Date, index=True)
    cliente_nit: Mapped[str] = mapped_column(String(32))
    totales_por_bucket: Mapped[dict] = mapped_column(JSON, default=dict)
    cartera_total: Mapped[Decimal] = mapped_column(DINERO)
    generado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    version_parametros: Mapped[str] = mapped_column(String(64))
    """Huella de la configuracion con que se calculo el corte.

    Sin ella, dos snapshots del mismo corte con umbrales distintos serian
    indistinguibles y la reproduccion dejaria de ser explicable.
    """


class Gestion(Base):
    """Historial de cobranza (§11). Base de A12, que es de fase 5."""

    __tablename__ = "ar_gestion"
    __table_args__ = (
        Index("ix_gestion_cliente_fecha", "cliente_nit", "fecha"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[str] = mapped_column(String(32))
    alerta_id: Mapped[int | None] = mapped_column(Integer)
    cliente_nit: Mapped[str] = mapped_column(String(32))
    factura: Mapped[str] = mapped_column(String(32), default=SIN_FACTURA)
    fecha: Mapped[datetime] = mapped_column(DateTime)
    usuario_id: Mapped[str] = mapped_column(String(64))
    tipo: Mapped[str] = mapped_column(String(32))
    resultado: Mapped[str | None] = mapped_column(String(64))
    compromiso_fecha: Mapped[date | None] = mapped_column(Date)
    compromiso_valor: Mapped[Decimal | None] = mapped_column(DINERO)
    observacion: Mapped[str | None] = mapped_column(Text)


class AuditoriaConfig(Base):
    """Quien cambio que parametro, cuando, y de que valor a cual (§10.3)."""

    __tablename__ = "ar_auditoria_config"
    __table_args__ = (
        Index("ix_auditoria_empresa_fecha", "empresa_id", "fecha_hora"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[str] = mapped_column(String(32))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    usuario_id: Mapped[str] = mapped_column(String(64))
    entidad: Mapped[str] = mapped_column(String(32))
    campo: Mapped[str] = mapped_column(String(64))
    valor_anterior: Mapped[str | None] = mapped_column(Text)
    valor_nuevo: Mapped[str | None] = mapped_column(Text)


class Ejecucion(Base):
    """Bitacora de corridas del motor (§10.2)."""

    __tablename__ = "ar_ejecucion"
    __table_args__ = (
        Index("ix_ejecucion_empresa_corte", "empresa_id", "corte"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[str] = mapped_column(String(32))
    corte: Mapped[date] = mapped_column(Date)
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fin: Mapped[datetime | None] = mapped_column(DateTime)
    filas_procesadas: Mapped[int] = mapped_column(Integer, default=0)
    alertas_generadas: Mapped[int] = mapped_column(Integer, default=0)
    alertas_cerradas: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[str] = mapped_column(String(16), default="en_curso")
    mensaje: Mapped[str | None] = mapped_column(Text)
