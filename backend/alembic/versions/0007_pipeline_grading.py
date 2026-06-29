"""Agrega pipeline de preprocesamiento y calificación (US 191, US 193).

Extiende `evaluaciones` con los campos del pipeline de Sprint 4 y crea
`grading_baselines` para el ground truth calibrado por (set, acabado)
usado en la selección de baseline de US 193.

Revision ID: 0007_pipeline_grading
Revises: 0006_b2b_cuentas
Create Date: 2026-06-XX
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0007_pipeline_grading"
down_revision = "0006_b2b_cuentas"
branch_labels = None
depends_on = None

# Versión inicial del algoritmo de grading (DA-08: versionado controlado).
# Se persiste como string libre, no enum, para no requerir migración al
# liberar versiones futuras.
VERSION_ALGORITMO_INICIAL = "v1.0"


def upgrade() -> None:
    # --- Extender evaluaciones con campos del pipeline ---
    op.add_column(
        "evaluaciones",
        sa.Column("clave_blob_frente_procesada", sa.Text, nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("clave_blob_reverso_procesada", sa.Text, nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("regiones_segmentadas", JSONB, nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("motivo_revision_manual", sa.Text, nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("motivo_rechazo", sa.Text, nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("subgrade_centering", sa.Float, nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("subgrade_corners", sa.Float, nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("subgrade_edges", sa.Float, nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("subgrade_surface", sa.Float, nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("grado_estimado", sa.Float, nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("banda_incertidumbre", sa.Float, nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("version_algoritmo_grading", sa.String(20), nullable=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column("clave_idempotencia", sa.String(64), nullable=True, unique=True),
    )
    op.add_column(
        "evaluaciones",
        sa.Column(
            "reevaluacion_de_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluaciones.id"),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_evaluaciones_clave_idempotencia",
        "evaluaciones",
        ["clave_idempotencia"],
        unique=True,
    )

    # --- Crear grading_baselines ---
    op.create_table(
        "grading_baselines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("set_codigo", sa.String(50), nullable=True),
        sa.Column("acabado", sa.String(20), nullable=True),
        sa.Column("referencia_centering", sa.Float, nullable=False),
        sa.Column("referencia_corners", sa.Float, nullable=False),
        sa.Column("referencia_edges", sa.Float, nullable=False),
        sa.Column("referencia_surface", sa.Float, nullable=False),
        sa.Column("tamano_muestra", sa.Integer, nullable=False, server_default="0"),
        sa.Column("version_algoritmo", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_grading_baselines_set_acabado",
        "grading_baselines",
        ["set_codigo", "acabado"],
        unique=True,
    )

    # Seed del baseline global (fallback universal, set_codigo=NULL).
    # Valores iniciales neutros (0.7 en escala 0-1) hasta que haya
    # suficiente histórico de evaluaciones reales para recalibrar.
    grading_baselines = sa.table(
        "grading_baselines",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("set_codigo", sa.String),
        sa.column("acabado", sa.String),
        sa.column("referencia_centering", sa.Float),
        sa.column("referencia_corners", sa.Float),
        sa.column("referencia_edges", sa.Float),
        sa.column("referencia_surface", sa.Float),
        sa.column("tamano_muestra", sa.Integer),
        sa.column("version_algoritmo", sa.String),
    )
    op.bulk_insert(
        grading_baselines,
        [
            {
                "id": uuid.uuid4(),
                "set_codigo": None,
                "acabado": None,
                "referencia_centering": 0.7,
                "referencia_corners": 0.7,
                "referencia_edges": 0.7,
                "referencia_surface": 0.7,
                "tamano_muestra": 0,
                "version_algoritmo": VERSION_ALGORITMO_INICIAL,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("grading_baselines")

    op.drop_index("ix_evaluaciones_clave_idempotencia", table_name="evaluaciones")

    for columna in (
        "reevaluacion_de_id",
        "clave_idempotencia",
        "version_algoritmo_grading",
        "banda_incertidumbre",
        "grado_estimado",
        "subgrade_surface",
        "subgrade_edges",
        "subgrade_corners",
        "subgrade_centering",
        "motivo_rechazo",
        "motivo_revision_manual",
        "regiones_segmentadas",
        "clave_blob_reverso_procesada",
        "clave_blob_frente_procesada",
    ):
        op.drop_column("evaluaciones", columna)
