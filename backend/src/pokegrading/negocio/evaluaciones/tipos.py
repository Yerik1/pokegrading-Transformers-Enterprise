"""Tipos de dominio del pipeline de evaluación (preprocesamiento + calificación).

Los estados se modelan como enum de Python (no enum de PostgreSQL) para
que agregar un estado nuevo no requiera una migración de tipo; el campo
`Evaluacion.estado` es un `String` simple y este enum es la única fuente
de verdad sobre qué valores son válidos.
"""

from __future__ import annotations

from enum import StrEnum


class EstadoEvaluacion(StrEnum):
    """Estados del pipeline. Ver diagrama de transición en modelos.py."""

    PENDIENTE = "pendiente"
    PREPROCESANDO = "preprocesando"
    CALIFICANDO = "calificando"
    COMPLETADA = "completada"
    REVISION_MANUAL = "revision_manual"
    RECHAZADA = "rechazada"


class RegionCarta(StrEnum):
    """Las cuatro regiones segmentadas durante el preprocesamiento (US 191).

    Mismo nombre que las cuatro dimensiones de subgrade calificadas en
    US 193: cada región segmentada alimenta directamente su subgrade
    correspondiente.
    """

    CENTERING = "centering"
    CORNERS = "corners"
    EDGES = "edges"
    SURFACE = "surface"


class CaraCarta(StrEnum):
    """Frente o reverso. El preprocesamiento y la calificación procesan
    ambas caras de forma independiente.
    """

    FRENTE = "frente"
    REVERSO = "reverso"
