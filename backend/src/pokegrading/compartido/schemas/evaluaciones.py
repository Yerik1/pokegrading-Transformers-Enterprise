"""Schemas Pydantic para el módulo de evaluaciones."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EnviarCartaResponse(BaseModel):
    """Respuesta al enviar una carta para evaluación.

    Incluye tanto los datos del envío inicial (Sprint 3) como el resultado
    del pipeline completo de preprocesamiento y calificación (Sprint 4,
    US 191 y US 193). El pipeline corre de forma síncrona dentro de la
    misma request, por lo que el estado final ya está disponible aquí.
    """

    # --- Datos del envío (Sprint 3) ---
    identificador_evaluacion: str = Field(
        description="Identificador único de la evaluación (ej. EV-2026-05-31-A1B3)."
    )
    estado: str = Field(
        description=(
            "Estado final del pipeline: 'completada', 'revision_manual' o 'rechazada'."
        )
    )
    iq_score_frente: float = Field(description="Image Quality Score del frente.")
    iq_score_reverso: float = Field(description="Image Quality Score del reverso.")
    mensaje: str = Field(description="Confirmación de recepción para el usuario.")
    tiempo_estimado_segundos: int | None = Field(
        default=None,
        description="Tiempo estimado de procesamiento si el sistema está saturado.",
    )
    created_at: datetime

    # --- Resultado del pipeline (Sprint 4 — US 191 / US 193) ---
    grado_estimado: float | None = Field(
        default=None,
        description=(
            "Grado estimado en escala 1.0–10.0 (US 193). "
            "None si la evaluación fue derivada a revisión manual."
        ),
    )
    banda_incertidumbre: float | None = Field(
        default=None,
        description=(
            "Banda de incertidumbre del grado estimado. "
            "El grado real del mercado está dentro de [grado ± banda]."
        ),
    )
    subgrade_centering: float | None = Field(
        default=None, description="Subgrade de centrado en escala 1.0–10.0."
    )
    subgrade_corners: float | None = Field(
        default=None, description="Subgrade de esquinas en escala 1.0–10.0."
    )
    subgrade_edges: float | None = Field(
        default=None, description="Subgrade de bordes en escala 1.0–10.0."
    )
    subgrade_surface: float | None = Field(
        default=None, description="Subgrade de superficie en escala 1.0–10.0."
    )
    version_algoritmo_grading: str | None = Field(
        default=None,
        description=(
            "Versión del algoritmo de grading usado (DA-08). "
            "Inmutable: liberar una versión nueva no modifica este campo."
        ),
    )
