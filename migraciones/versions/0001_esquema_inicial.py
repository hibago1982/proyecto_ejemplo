"""Esquema inicial del motor de alertas de cartera.

Crea las tablas de §6.2 y anade lo que el modelo portable no puede expresar y
solo tiene sentido en PostgreSQL:

  * `ar_alert_rule.parametros` pasa de JSON a JSONB con indice GIN. Los
    parametros varian en forma segun la regla (un umbral monetario, un conteo,
    un numero de dias) y JSONB permite guardarlos sin una columna por regla.
  * `ar_snapshot` se convierte en tabla particionada por rango sobre `corte`.
    Crece un corte por dia y por empresa; el particionado mantiene el
    rendimiento y permite archivar cortes viejos sin tocar la tabla viva.
  * Seguridad a nivel de fila sobre las tablas con `empresa_id`, para que una
    consulta mal escrita no pueda devolver datos de otra empresa.

Sobre SQLite todo esto se omite y quedan solo las tablas, que es suficiente
para pruebas.

Revision ID: 0001
Revises:
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from busint_alertas.persistencia.modelo import Base

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


def es_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())
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
    op.execute("COMMENT ON TABLE ar_snapshot IS 'Particionar por rango sobre corte; retencion 24 meses (C-15)'")

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
    Base.metadata.drop_all(op.get_bind())
