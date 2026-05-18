"""inicial usuarios

Revision ID: 0001_inicial_usuarios
Revises:
Create Date: 2026-05-17

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_inicial_usuarios"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Crear los tipos enum explícitamente con checkfirst para soportar reruns parciales.
    pais_enum = postgresql.ENUM(
        "CR", "PA", "MX", "CO", "CL", "AR",
        name="pais_enum",
        create_type=False,
    )
    idioma_enum = postgresql.ENUM(
        "es", "en",
        name="idioma_enum",
        create_type=False,
    )
    rol_enum = postgresql.ENUM(
        "submitter", "reviewer", "admin", "b2b_service_account",
        name="rol_enum",
        create_type=False,
    )

    bind = op.get_bind()
    pais_enum.create(bind, checkfirst=True)
    idioma_enum.create(bind, checkfirst=True)
    rol_enum.create(bind, checkfirst=True)

    op.create_table(
        "usuarios",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("correo", sa.String(length=254), nullable=False),
        sa.Column("alias", sa.String(length=50), nullable=False),
        sa.Column("hash_password", sa.String(length=255), nullable=False),
        sa.Column("pais", pais_enum, nullable=False),
        sa.Column(
            "idioma_preferido",
            idioma_enum,
            nullable=False,
            server_default="es",
        ),
        sa.Column(
            "rol",
            rol_enum,
            nullable=False,
            server_default="submitter",
        ),
        sa.Column("disclosure_aceptado", sa.Boolean(), nullable=False),
        sa.Column("disclosure_version", sa.String(length=20), nullable=False),
        sa.Column(
            "disclosure_aceptado_en",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_usuarios_correo", "usuarios", ["correo"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_usuarios_correo", table_name="usuarios")
    op.drop_table("usuarios")
    postgresql.ENUM(name="rol_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="idioma_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="pais_enum").drop(op.get_bind(), checkfirst=True)