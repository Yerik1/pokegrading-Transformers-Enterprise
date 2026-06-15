"""Tablas B2B: cuentas, auditoría de consultas y rate limiting.

Revision ID: 0006_b2b_cuentas
Revises: 0005_evaluaciones
Create Date: 2026-06-15

Crea tres tablas:
- b2b_cuentas: tiendas con API key hasheada (SHA-256)
- b2b_consultas_auditoria: registro append-only de cada lookup
- b2b_rate_limit: contadores mensuales por cuenta
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0006_b2b_cuentas"
down_revision: str | None = "0005_evaluaciones"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # --- b2b_cuentas ---
    op.create_table(
        "b2b_cuentas",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("nombre_tienda", sa.String(200), nullable=False),
        sa.Column("api_key_hash", sa.String(64), nullable=False),
        sa.Column("api_key_prefijo", sa.String(8), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("suspendida", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("motivo_suspension", sa.Text(), nullable=True),
        sa.Column("limite_cartas_mes", sa.Integer(), nullable=False, server_default="10000"),
        sa.Column("ventana_idempotencia_segundos", sa.Integer(), nullable=False, server_default="300"),
        sa.Column(
            "usuario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_b2b_cuentas_api_key_hash", "b2b_cuentas", ["api_key_hash"], unique=True)

    # --- b2b_consultas_auditoria ---
    op.create_table(
        "b2b_consultas_auditoria",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "cuenta_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("b2b_cuentas.id"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("total_cartas", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("respuesta_json", sa.Text(), nullable=False),
        sa.Column("es_reintento", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("cuenta_id", "idempotency_key", name="uq_b2b_idempotencia"),
    )
    op.create_index(
        "ix_b2b_consultas_auditoria_cuenta_id",
        "b2b_consultas_auditoria",
        ["cuenta_id"],
    )
    op.create_index(
        "ix_b2b_consultas_auditoria_idempotency_key",
        "b2b_consultas_auditoria",
        ["idempotency_key"],
    )

    # --- b2b_rate_limit ---
    op.create_table(
        "b2b_rate_limit",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "cuenta_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("b2b_cuentas.id"),
            nullable=False,
        ),
        sa.Column("anio", sa.Integer(), nullable=False),
        sa.Column("mes", sa.Integer(), nullable=False),
        sa.Column("cartas_consultadas", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("cuenta_id", "anio", "mes", name="uq_b2b_rate_limit_mes"),
    )
    op.create_index(
        "ix_b2b_rate_limit_cuenta_id", "b2b_rate_limit", ["cuenta_id"]
    )


def downgrade() -> None:
    op.drop_table("b2b_rate_limit")
    op.drop_table("b2b_consultas_auditoria")
    op.drop_table("b2b_cuentas")