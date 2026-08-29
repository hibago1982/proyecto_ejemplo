"""Esquema inicial del motor de alertas de cartera.

Crea las entidades de §6.2. Las tablas se declaran aqui de forma explicita y no
con `Base.metadata.create_all`: una migracion tiene que describir el esquema tal
como era en su revision, no como esta el modelo hoy. Con `create_all` esta
revision iba mutando con cada cambio del modelo, y en una base nueva la 0002
fallaba al anadir una columna que la 0001 ya habia creado.

Ademas se anade lo que el modelo portable no puede expresar y solo tiene sentido
en PostgreSQL:

  * `ar_alert_rule.parametros` pasa de JSON a JSONB con indice GIN. Los
    parametros varian en forma segun la regla (un umbral monetario, un conteo,
    un numero de dias) y JSONB permite guardarlos sin una columna por regla.
  * Seguridad a nivel de fila sobre las tablas con `empresa_id`, para que una
    consulta mal escrita no pueda devolver datos de otra empresa.

Sobre SQLite todo eso se omite y quedan solo las tablas, que basta para pruebas.

Revision ID: 0001
Revises:
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

#: Tablas aisladas por empresa. §8.1 exige el filtro; C-08 lo hace obligatorio.
TABLAS_MULTIEMPRESA = (
    "ar_aging_param",
    "ar_alert_rule",
    "ar_alerta",
    "ar_riesgo_cliente",
    "ar_snapshot",
    "ar_gestion",
    "ar_auditoria_config",
    "ar_ejecucion",
)

#: En orden inverso al de creacion, para el downgrade.
TABLAS = (
    "ar_aging_param",
    "ar_alert_rule",
    "ar_alerta",
    "ar_auditoria_config",
    "ar_ejecucion",
    "ar_gestion",
    "ar_riesgo_cliente",
    "ar_snapshot",
)


def es_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "ar_aging_param",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.String(length=32), nullable=False),
        sa.Column("codigo", sa.String(length=8), nullable=False),
        sa.Column("etiqueta", sa.String(length=64), nullable=False),
        sa.Column("desde", sa.Integer(), nullable=True),
        sa.Column("hasta", sa.Integer(), nullable=True),
        sa.Column("color", sa.String(length=16), nullable=False),
        sa.Column("prioridad_base", sa.Integer(), nullable=False),
        sa.Column("accion", sa.String(length=64), nullable=False),
        sa.Column("alerta", sa.String(length=8), nullable=True),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("empresa_id", "codigo", name="uq_aging_empresa_codigo"),
    )
    op.create_index("ix_ar_aging_param_empresa_id", "ar_aging_param", ["empresa_id"])

    op.create_table(
        "ar_alert_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.String(length=32), nullable=False),
        sa.Column("codigo", sa.String(length=8), nullable=False),
        sa.Column("tipo", sa.String(length=16), nullable=False),
        sa.Column("parametros", sa.JSON(), nullable=False),
        sa.Column("prioridad", sa.Integer(), nullable=False),
        sa.Column("accion", sa.String(length=64), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("empresa_id", "codigo", name="uq_rule_empresa_codigo"),
    )
    op.create_index("ix_ar_alert_rule_empresa_id", "ar_alert_rule", ["empresa_id"])

    op.create_table(
        "ar_alerta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.String(length=32), nullable=False),
        sa.Column("corte", sa.Date(), nullable=False),
        sa.Column("cliente_nit", sa.String(length=32), nullable=False),
        sa.Column("factura", sa.String(length=32), nullable=False),
        sa.Column("regla", sa.String(length=8), nullable=False),
        sa.Column("codigo", sa.String(length=8), nullable=False),
        sa.Column("etiqueta", sa.String(length=64), nullable=False),
        sa.Column("prioridad", sa.Integer(), nullable=False),
        sa.Column("accion", sa.String(length=64), nullable=False),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("bucket", sa.String(length=8), nullable=True),
        sa.Column("dias", sa.Integer(), nullable=True),
        sa.Column("saldo", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("saldo_bruto", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("credito_aplicado", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("origen_dias", sa.String(length=16), nullable=False),
        sa.Column("explicacion", sa.Text(), nullable=True),
        sa.Column("datos", sa.JSON(), nullable=False),
        sa.Column("detectado_pago", sa.Date(), nullable=True),
        sa.Column("actualizado", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("empresa_id", "corte", "cliente_nit", "factura", "regla", name="uq_alerta_clave_logica"),
    )
    op.create_index("ix_alerta_cliente", "ar_alerta", ["empresa_id", "cliente_nit", "corte"])
    op.create_index("ix_alerta_panel", "ar_alerta", ["empresa_id", "corte", "prioridad"])

    op.create_table(
        "ar_auditoria_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.String(length=32), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(), nullable=False),
        sa.Column("usuario_id", sa.String(length=64), nullable=False),
        sa.Column("entidad", sa.String(length=32), nullable=False),
        sa.Column("campo", sa.String(length=64), nullable=False),
        sa.Column("valor_anterior", sa.Text(), nullable=True),
        sa.Column("valor_nuevo", sa.Text(), nullable=True),
    )
    op.create_index("ix_auditoria_empresa_fecha", "ar_auditoria_config", ["empresa_id", "fecha_hora"])

    op.create_table(
        "ar_ejecucion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.String(length=32), nullable=False),
        sa.Column("corte", sa.Date(), nullable=False),
        sa.Column("inicio", sa.DateTime(), nullable=False),
        sa.Column("fin", sa.DateTime(), nullable=True),
        sa.Column("filas_procesadas", sa.Integer(), nullable=False),
        sa.Column("alertas_generadas", sa.Integer(), nullable=False),
        sa.Column("alertas_cerradas", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=16), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=True),
    )
    op.create_index("ix_ejecucion_empresa_corte", "ar_ejecucion", ["empresa_id", "corte"])

    op.create_table(
        "ar_gestion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.String(length=32), nullable=False),
        sa.Column("alerta_id", sa.Integer(), nullable=True),
        sa.Column("cliente_nit", sa.String(length=32), nullable=False),
        sa.Column("factura", sa.String(length=32), nullable=False),
        sa.Column("fecha", sa.DateTime(), nullable=False),
        sa.Column("usuario_id", sa.String(length=64), nullable=False),
        sa.Column("tipo", sa.String(length=32), nullable=False),
        sa.Column("resultado", sa.String(length=64), nullable=True),
        sa.Column("compromiso_fecha", sa.Date(), nullable=True),
        sa.Column("compromiso_valor", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("observacion", sa.Text(), nullable=True),
    )
    op.create_index("ix_gestion_cliente_fecha", "ar_gestion", ["cliente_nit", "fecha"])

    op.create_table(
        "ar_riesgo_cliente",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.String(length=32), nullable=False),
        sa.Column("corte", sa.Date(), nullable=False),
        sa.Column("cliente_nit", sa.String(length=32), nullable=False),
        sa.Column("cliente_nombre", sa.String(length=128), nullable=False),
        sa.Column("cartera_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("por_vencer", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("vence_hoy", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("vencida", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("pct_vencida", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column("mayor_90", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("pct_90", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column("mayor_150", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("dias_max", sa.Integer(), nullable=False),
        sa.Column("n_facturas", sa.Integer(), nullable=False),
        sa.Column("n_vencidas", sa.Integer(), nullable=False),
        sa.Column("prioridad", sa.Integer(), nullable=False),
        sa.Column("marcadores", sa.JSON(), nullable=False),
        sa.UniqueConstraint("empresa_id", "corte", "cliente_nit", name="uq_riesgo_clave"),
    )
    op.create_index("ix_riesgo_ranking", "ar_riesgo_cliente", ["empresa_id", "corte", "prioridad"])

    op.create_table(
        "ar_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.String(length=32), nullable=False),
        sa.Column("corte", sa.Date(), nullable=False),
        sa.Column("cliente_nit", sa.String(length=32), nullable=False),
        sa.Column("totales_por_bucket", sa.JSON(), nullable=False),
        sa.Column("cartera_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("generado", sa.DateTime(), nullable=False),
        sa.Column("version_parametros", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("empresa_id", "corte", "cliente_nit", name="uq_snapshot_clave"),
    )
    op.create_index("ix_ar_snapshot_corte", "ar_snapshot", ["corte"])

    if not es_postgres():
        return

    # JSONB en vez de JSON: indexable, y es donde viven los umbrales de reglas.
    op.execute(
        "ALTER TABLE ar_alert_rule "
        "ALTER COLUMN parametros TYPE jsonb USING parametros::jsonb"
    )
    op.execute(
        "CREATE INDEX ix_alert_rule_parametros "
        "ON ar_alert_rule USING gin (parametros jsonb_path_ops)"
    )
    op.execute("ALTER TABLE ar_alerta ALTER COLUMN datos TYPE jsonb USING datos::jsonb")

    # Retencion de 24 meses (C-15): el particionado permite soltar particiones
    # viejas en vez de borrar filas de una tabla en uso.
    op.execute(
        "COMMENT ON TABLE ar_snapshot IS "
        "'Particionar por rango sobre corte; retencion 24 meses (C-15)'"
    )

    _activar_seguridad_por_fila()


def _activar_seguridad_por_fila() -> None:
    """Aislamiento multiempresa como red de seguridad, no como convencion.

    El motor ya filtra por empresa, pero una consulta futura mal escrita en el
    API no deberia poder devolver la cartera de otro cliente.
    """
    op.execute("CREATE ROLE busint_app NOLOGIN")
    for tabla in TABLAS_MULTIEMPRESA:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY aislamiento_empresa ON {tabla} FOR ALL TO busint_app "
            f"USING (empresa_id = current_setting('busint.empresa_id', true))"
        )


def downgrade() -> None:
    if es_postgres():
        for tabla in TABLAS_MULTIEMPRESA:
            op.execute(f"DROP POLICY IF EXISTS aislamiento_empresa ON {tabla}")
            op.execute(f"ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY")
        op.execute("DROP INDEX IF EXISTS ix_alert_rule_parametros")
        op.execute("DROP ROLE IF EXISTS busint_app")
    for tabla in reversed(TABLAS):
        op.drop_table(tabla)
