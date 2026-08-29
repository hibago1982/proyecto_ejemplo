"""Campos que exige la fase de gestion y la activacion de A12.

Dos columnas nuevas:

  * `ar_alerta.primer_corte` — desde cuando esta activa una alerta. Es la
    referencia de A12 cuando la factura nunca se ha gestionado. Sin ella habria
    que recorrer los cortes anteriores en cada corrida.
  * `ar_gestion.corte` — en que corte se registro la gestion, para poder
    reproducir el estado de un corte pasado tambien en lo que toca a gestion.

Y un indice sobre `ar_gestion` por factura y fecha descendente: es la consulta
que arma el historial en cada corrida, y sin el degrada a medida que crece la
bitacora de cobranza.

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ar_alerta", sa.Column("primer_corte", sa.Date(), nullable=True))
    op.add_column("ar_gestion", sa.Column("corte", sa.Date(), nullable=True))

    # Las alertas ya escritas no tienen primer_corte. Se rellena con su propio
    # corte: es lo mas conservador, porque hace que A12 empiece a contar desde
    # esta migracion en vez de disparar de golpe sobre cartera antigua.
    op.execute("UPDATE ar_alerta SET primer_corte = corte WHERE primer_corte IS NULL")

    op.create_index(
        "ix_gestion_factura_fecha",
        "ar_gestion",
        ["empresa_id", "cliente_nit", "factura", "fecha"],
    )


def downgrade() -> None:
    op.drop_index("ix_gestion_factura_fecha", table_name="ar_gestion")
    op.drop_column("ar_gestion", "corte")
    op.drop_column("ar_alerta", "primer_corte")
