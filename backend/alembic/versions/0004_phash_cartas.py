"""Agrega columna phash_frente a cartas_catalogo para búsqueda rápida.

Revision ID: 0004_phash_cartas
Revises: 0003_cartas_catalogo
Create Date: 2026-05-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_phash_cartas"
down_revision = "0003_cartas_catalogo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cartas_catalogo",
        sa.Column("phash_frente", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cartas_catalogo", "phash_frente")
