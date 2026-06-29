"""Modelos ORM del módulo evaluaciones.

`Evaluacion` registra cada solicitud de evaluación enviada por un Submitter.
Inmutable tras su creación (DA-03): los resultados del pipeline se agregan
como campos opcionales, nunca se modifica la información original que envió
el usuario. Si se solicita una re-evaluación, se crea un registro nuevo
vinculado al original (`reevaluacion_de_id`); el histórico no se toca.

Pipeline de estados (Sprint 4 — US 191 Preprocesar, US 193 Calificar):

    pendiente
        │
        ▼
    preprocesando ──[no se puede aislar del fondo]──► revision_manual
        │
        ▼ [preprocesamiento exitoso]
    calificando ──[distorsión imposible de corregir]──► rechazada
        │
        ▼ [subgrades calculados]
    completada ──[subgrade no calculable o incoherencia]──► revision_manual
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pokegrading.datos.db import Base

# Estados válidos del pipeline. String simple (no Enum de BD) para no
# requerir una migración de tipo cada vez que se agregue un estado;
# la validez se controla en `negocio/evaluaciones/tipos.py`.
ESTADOS_EVALUACION: frozenset[str] = frozenset(
    {
        "pendiente",
        "preprocesando",
        "calificando",
        "completada",
        "revision_manual",
        "rechazada",
    }
)


class Evaluacion(Base):
    """Solicitud de evaluación de una carta."""

    __tablename__ = "evaluaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    identificador_evaluacion: Mapped[str] = mapped_column(
        String(30), nullable=False, unique=True
    )
    submitter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pendiente"
    )

    # --- Imágenes originales (Sprint 3) ---
    url_imagen_frente: Mapped[str] = mapped_column(Text, nullable=False)
    clave_blob_frente: Mapped[str] = mapped_column(Text, nullable=False)
    url_imagen_reverso: Mapped[str] = mapped_column(Text, nullable=False)
    clave_blob_reverso: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    iq_score_frente: Mapped[float | None] = mapped_column(Float, nullable=True)
    iq_score_reverso: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Preprocesamiento (Sprint 4 — US 191) ---
    clave_blob_frente_procesada: Mapped[str | None] = mapped_column(Text, nullable=True)
    clave_blob_reverso_procesada: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    regiones_segmentadas: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    motivo_revision_manual: Mapped[str | None] = mapped_column(Text, nullable=True)
    motivo_rechazo: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Calificación (Sprint 4 — US 193) ---
    subgrade_centering: Mapped[float | None] = mapped_column(Float, nullable=True)
    subgrade_corners: Mapped[float | None] = mapped_column(Float, nullable=True)
    subgrade_edges: Mapped[float | None] = mapped_column(Float, nullable=True)
    subgrade_surface: Mapped[float | None] = mapped_column(Float, nullable=True)
    grado_estimado: Mapped[float | None] = mapped_column(Float, nullable=True)
    banda_incertidumbre: Mapped[float | None] = mapped_column(Float, nullable=True)
    version_algoritmo_grading: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    baseline_id_usado: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grading_baselines.id"), nullable=True
    )
    clave_idempotencia: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    reevaluacion_de_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluaciones.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Evaluacion id={self.id} "
            f"{self.identificador_evaluacion} estado={self.estado}>"
        )


class GradingBaseline(Base):
    """Baseline calibrado de subgrades por (set_codigo, acabado).

    Usado por US 193 para comparar las métricas objetivas calculadas
    contra un "ground truth" calibrado del mismo set/acabado, cuando
    hay suficiente histórico. Si no hay baseline específico, el
    servicio usa el baseline global (set_codigo NULL) como fallback.
    """

    __tablename__ = "grading_baselines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    set_codigo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    acabado: Mapped[str | None] = mapped_column(String(20), nullable=True)

    referencia_centering: Mapped[float] = mapped_column(Float, nullable=False)
    referencia_corners: Mapped[float] = mapped_column(Float, nullable=False)
    referencia_edges: Mapped[float] = mapped_column(Float, nullable=False)
    referencia_surface: Mapped[float] = mapped_column(Float, nullable=False)

    tamano_muestra: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    version_algoritmo: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        ident = f"{self.set_codigo}/{self.acabado}" if self.set_codigo else "global"
        return f"<GradingBaseline {ident} v{self.version_algoritmo}>"
