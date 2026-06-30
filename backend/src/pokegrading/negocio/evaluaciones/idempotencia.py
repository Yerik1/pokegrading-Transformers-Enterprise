"""Clave de idempotencia del pipeline de evaluación (US 193).

Extraída a su propio módulo porque la usan dos lugares distintos:

1. `PipelineEvaluacionService` (chequeo TEMPRANO, antes de crear ningún
   registro ni subir nada a Blob Storage) — evita crear una fila
   duplicada en `evaluaciones` cuando el mismo submitter reenvía la
   misma carta.
2. `CalificarCartaService` (chequeo de RESPALDO, ya con la evaluación
   creada) — sigue ahí como red de seguridad por si dos envíos
   idénticos llegan en paralelo y ambos pasan el chequeo temprano antes
   de que el primero termine de persistirse (condición de carrera poco
   probable, pero el respaldo evita que se vuelva a calcular el grado
   dos veces).

Una sola función pura, sin dependencias de SQLAlchemy ni de Blob
Storage, para que ambos lugares calculen exactamente la misma clave
a partir de los mismos datos.
"""

from __future__ import annotations

import hashlib
import uuid


def calcular_clave_idempotencia(
    submitter_id: uuid.UUID, bytes_frente: bytes, bytes_reverso: bytes
) -> str:
    """Deriva una clave determinística de (submitter, contenido real de
    las imágenes).

    Dos envíos de la misma carta por el mismo submitter producen la
    misma clave, sin que el cliente tenga que mandar un identificador
    explícito. Se hashea el CONTENIDO de los bytes, no rutas de blob
    ni IDs de evaluación — esos cambian en cada envío aunque la carta
    física sea la misma.
    """
    hasher = hashlib.sha256()
    hasher.update(str(submitter_id).encode("utf-8"))
    hasher.update(bytes_frente)
    hasher.update(bytes_reverso)
    return hasher.hexdigest()
