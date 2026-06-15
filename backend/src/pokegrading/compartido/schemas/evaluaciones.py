"""Schemas Pydantic para el módulo de evaluaciones."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EnviarCartaResponse(BaseModel):
    """Respuesta al enviar una carta para evaluación."""

    identificador_evaluacion: str = Field(
        description="Identificador único de la evaluación (ej. EV-2026-05-31-A1B3)."
    )
    estado: str = Field(description="Estado inicial de la evaluación.")
    iq_score_frente: float = Field(description="Image Quality Score del frente.")
    iq_score_reverso: float = Field(description="Image Quality Score del reverso.")
    mensaje: str = Field(description="Confirmación de recepción para el usuario.")
    tiempo_estimado_segundos: int | None = Field(
        default=None,
        description="Tiempo estimado de procesamiento si el sistema está saturado.",
    )
    created_at: datetime
