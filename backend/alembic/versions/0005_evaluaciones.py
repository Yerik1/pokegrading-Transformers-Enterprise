"""Crea tabla evaluaciones para el flujo de envío de cartas.

Revision ID: 0005_evaluaciones
Revises: 0004_phash_cartas
Create Date: 2026-05-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0005_evaluaciones"
down_revision = "0004_phash_cartas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluaciones",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("identificador_evaluacion", sa.String(30), nullable=False, unique=True),
        sa.Column("submitter_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="recibida"),
        sa.Column("url_imagen_frente", sa.Text, nullable=False),
        sa.Column("clave_blob_frente", sa.Text, nullable=False),
        sa.Column("url_imagen_reverso", sa.Text, nullable=False),
        sa.Column("clave_blob_reverso", sa.Text, nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("iq_score_frente", sa.Float, nullable=True),
        sa.Column("iq_score_reverso", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evaluaciones_submitter_id", "evaluaciones", ["submitter_id"])
    op.create_index("ix_evaluaciones_estado", "evaluaciones", ["estado"])


def downgrade() -> None:
    op.drop_index("ix_evaluaciones_estado", "evaluaciones")
    op.drop_index("ix_evaluaciones_submitter_id", "evaluaciones")
    op.drop_table("evaluaciones")
