"""cartas_catalogo

Revision ID: 0003_cartas_catalogo
Revises: 0002_agregar_superadmin
Create Date: 2026-05-18

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_cartas_catalogo"
down_revision: Union[str, None] = "0002_agregar_superadmin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Crear los 5 enums nuevos. Usamos `create_type=False` en las columnas
    # para que sea esta migración (no `create_table`) la que los cree.
    edicion_enum = postgresql.ENUM(
        "1st_edition", "unlimited", "shadowless",
        name="edicion_enum",
        create_type=False,
    )
    idioma_carta_enum = postgresql.ENUM(
        "EN", "JP", "ES", "DE", "FR", "IT", "KR", "ZH_T",
        name="idioma_carta_enum",
        create_type=False,
    )
    acabado_enum = postgresql.ENUM(
        "holo", "reverse_holo", "full_art", "non_holo",
        name="acabado_enum",
        create_type=False,
    )
    rareza_enum = postgresql.ENUM(
        "common", "uncommon", "rare", "holo_rare", "ultra_rare", "secret_rare",
        name="rareza_enum",
        create_type=False,
    )
    tipo_pokemon_enum = postgresql.ENUM(
        "grass", "fire", "water", "lightning", "psychic", "fighting",
        "darkness", "metal", "fairy", "dragon", "colorless",
        name="tipo_pokemon_enum",
        create_type=False,
    )

    bind = op.get_bind()
    for enum in (
        edicion_enum,
        idioma_carta_enum,
        acabado_enum,
        rareza_enum,
        tipo_pokemon_enum,
    ):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "cartas_catalogo",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        # Identity tuple
        sa.Column("set_codigo", sa.String(length=50), nullable=False),
        sa.Column("numero", sa.String(length=20), nullable=False),
        sa.Column("edicion", edicion_enum, nullable=False),
        sa.Column("idioma", idioma_carta_enum, nullable=False),
        sa.Column("acabado", acabado_enum, nullable=False),
        # Display
        sa.Column("nombre", sa.String(length=100), nullable=True),
        sa.Column("rareza", rareza_enum, nullable=True),
        sa.Column("tipo", tipo_pokemon_enum, nullable=True),
        sa.Column("hp", sa.Integer(), nullable=True),
        sa.Column("ilustrador", sa.String(length=100), nullable=True),
        sa.Column("anio_impresion", sa.Integer(), nullable=True),
        # Imágenes
        sa.Column("url_imagen_frente", sa.Text(), nullable=False),
        sa.Column("clave_blob_frente", sa.Text(), nullable=False),
        sa.Column("url_imagen_reverso", sa.Text(), nullable=True),
        sa.Column("clave_blob_reverso", sa.Text(), nullable=True),
        # Auditoría
        sa.Column(
            "creada_por_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "set_codigo",
            "numero",
            "edicion",
            "idioma",
            "acabado",
            name="uq_cartas_identity_tuple",
        ),
    )


def downgrade() -> None:
    op.drop_table("cartas_catalogo")
    for enum_name in (
        "tipo_pokemon_enum",
        "rareza_enum",
        "acabado_enum",
        "idioma_carta_enum",
        "edicion_enum",
    ):
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
