"""Convierte a JSONB las dos columnas JSON que quedaron sin convertir.

La revision 0001 paso a JSONB `ar_alert_rule.parametros` y `ar_alerta.datos`,
pero dejo como `json` las otras dos. No fue una decision: fue un descuido, y se
noto al ejecutar las migraciones contra PostgreSQL por primera vez.

La diferencia importa aunque estas dos columnas se lean enteras y no se
consulten por dentro: `json` guarda el texto tal cual, con espacios y claves
repetidas, mientras `jsonb` lo normaliza y permite indexar. Tener dos columnas
de un tipo y dos de otro sin motivo es lo que hace que alguien mas adelante
dude de cual es el criterio.

Sobre SQLite no hay nada que hacer: alli las cuatro son texto igualmente.

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

COLUMNAS = (
    ("ar_riesgo_cliente", "marcadores"),
    ("ar_snapshot", "totales_por_bucket"),
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for tabla, columna in COLUMNAS:
        op.execute(
            f"ALTER TABLE {tabla} ALTER COLUMN {columna} "
            f"TYPE jsonb USING {columna}::jsonb"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for tabla, columna in COLUMNAS:
        op.execute(
            f"ALTER TABLE {tabla} ALTER COLUMN {columna} "
            f"TYPE json USING {columna}::json"
        )
