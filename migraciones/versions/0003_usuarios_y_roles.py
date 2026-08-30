"""Usuarios, roles y autenticacion (§8.4, C-13).

Cierra el hueco que el API arrastraba desde la etapa 3: la empresa llegaba en
una cabecera que el cliente controlaba. Con esta tabla la empresa y el rol salen
del token firmado.

La clave se guarda como PBKDF2-HMAC-SHA256 con sal por usuario. La columna es
ancha a proposito: si el proyecto migra a Argon2, el formato cabe sin migrar de
nuevo.

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ar_usuario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario", sa.String(length=64), nullable=False),
        sa.Column("empresa_id", sa.String(length=32), nullable=False),
        sa.Column("rol", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=128), nullable=False),
        sa.Column("clave_hash", sa.String(length=256), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("creado", sa.DateTime(), nullable=False),
        sa.Column("ultimo_acceso", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("usuario", name="uq_usuario_nombre"),
    )
    op.create_index("ix_ar_usuario_empresa_id", "ar_usuario", ["empresa_id"])

    if op.get_bind().dialect.name != "postgresql":
        return

    # La tabla de usuarios tambien se aisla por empresa: un administrador de una
    # empresa no debe poder listar los usuarios de otra.
    op.execute("ALTER TABLE ar_usuario ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY aislamiento_empresa ON ar_usuario FOR ALL TO busint_app "
        "USING (empresa_id = current_setting('busint.empresa_id', true))"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS aislamiento_empresa ON ar_usuario")
    op.drop_index("ix_ar_usuario_empresa_id", table_name="ar_usuario")
    op.drop_table("ar_usuario")
