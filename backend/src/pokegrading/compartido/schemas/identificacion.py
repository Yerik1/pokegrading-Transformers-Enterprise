"""Schemas Pydantic para el módulo de identificación."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CandidatoResponse(BaseModel):
    """Candidato retornado por la búsqueda rápida."""

    carta_id: str
    set_codigo: str
    numero: str
    nombre: str | None
    confianza: float = Field(ge=0.0, le=1.0)
    aceptado_automaticamente: bool


class BusquedaRapidaResponse(BaseModel):
    """Respuesta completa de la búsqueda rápida."""

    candidatos: list[CandidatoResponse]
    escala_a_especializada: bool = Field(
        description="True si ningún candidato superó el umbral de confianza."
    )
    deriva_a_manual: bool = Field(
        description="True si la imagen no permitió identificación visual."
    )
    umbral_usado: float
