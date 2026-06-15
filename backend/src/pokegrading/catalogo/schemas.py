"""Schemas Pydantic v2 para los endpoints del módulo `catalogo`."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from pokegrading.catalogo.tipos import (
    Acabado,
    Edicion,
    IdiomaCarta,
    Rareza,
    TipoPokemon,
)


class CrearCartaRequest(BaseModel):
    """Datos JSON enviados como parte del multipart form.

    El cuerpo del POST es `multipart/form-data` con un campo `datos`
    que contiene esta estructura serializada como JSON.
    """

    # Identity tuple (requerido)
    set_codigo: str = Field(min_length=1, max_length=50)
    numero: str = Field(min_length=1, max_length=20)
    edicion: Edicion
    idioma: IdiomaCarta
    acabado: Acabado

    # Display (opcional — la US los marca como "recomendados")
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    rareza: Rareza | None = None
    tipo: TipoPokemon | None = None
    hp: int | None = Field(
        default=None,
        ge=30,
        le=340,
        description="HP del Pokémon. Rango razonable según el TCG actual.",
    )
    ilustrador: str | None = Field(default=None, min_length=1, max_length=100)
    anio_impresion: int | None = Field(
        default=None,
        ge=1996,
        le=2030,
        description="Año entre 1996 (lanzamiento del TCG) y 2030.",
    )


class CartaResponse(BaseModel):
    """Representación pública de una carta del catálogo."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    set_codigo: str
    numero: str
    edicion: Edicion
    idioma: IdiomaCarta
    acabado: Acabado
    nombre: str | None
    rareza: Rareza | None
    tipo: TipoPokemon | None
    hp: int | None
    ilustrador: str | None
    anio_impresion: int | None
    url_imagen_frente: str
    url_imagen_reverso: str | None
    creada_por_id: uuid.UUID
    created_at: datetime
