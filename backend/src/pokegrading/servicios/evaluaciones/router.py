"""Router de evaluaciones de cartas.

El endpoint `/enviar` dispara el pipeline completo (Sprint 3 + Sprint 4):
envío → preprocesamiento (US 191) → calificación (US 193), todo dentro
de la misma request HTTP. No hay cola asíncrona en este sprint (DA-10,
escalabilidad horizontal, queda diferido); el cliente espera la
respuesta hasta que el pipeline corre por completo o se detiene en un
estado de revisión manual/rechazo.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.almacenamiento import (
    IAlmacenamientoImagenes,
    obtener_almacenamiento,
)
from pokegrading.compartido.dependencias import requerir_submitter_o_superior
from pokegrading.compartido.schemas.evaluaciones import EnviarCartaResponse
from pokegrading.datos.db import obtener_sesion
from pokegrading.negocio.evaluaciones.servicio_pipeline import PipelineEvaluacionService
from pokegrading.negocio.usuarios.modelos import Usuario

router = APIRouter(prefix="/api/v1/evaluaciones", tags=["evaluaciones"])


@router.post(
    "/enviar",
    response_model=EnviarCartaResponse,
    status_code=202,
    summary="Enviar carta para evaluación",
    description=(
        "Recibe las imágenes del frente y reverso de una carta y ejecuta "
        "el pipeline completo: validación, preprocesamiento (corrección "
        "de perspectiva, recorte, normalización y segmentación en 4 "
        "regiones) y calificación (subgrades + grado estimado). "
        "Si el sistema no logra aislar la carta del fondo o no puede "
        "calcular algún subgrade con confianza suficiente, la evaluación "
        "se deriva a revisión manual; si la imagen tiene una distorsión "
        "imposible de corregir, se rechaza y se solicita recapturar."
    ),
)
async def enviar_carta(
    request: Request,
    imagen_frente: Annotated[
        UploadFile, File(description="Imagen del frente de la carta")
    ],
    imagen_reverso: Annotated[
        UploadFile, File(description="Imagen del reverso de la carta")
    ],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
    almacenamiento: Annotated[IAlmacenamientoImagenes, Depends(obtener_almacenamiento)],
    usuario: Annotated[Usuario, Depends(requerir_submitter_o_superior)],
    set_codigo: Annotated[
        str | None,
        Form(
            description="Set de la carta, si se conoce (mejora la precisión del baseline)."
        ),
    ] = None,
    acabado: Annotated[
        str | None,
        Form(description="Acabado de la carta, si se conoce."),
    ] = None,
) -> EnviarCartaResponse:
    """Endpoint para enviar carta a evaluación y ejecutar el pipeline completo."""
    contenido_frente = await imagen_frente.read()
    contenido_reverso = await imagen_reverso.read()

    correlation_id = getattr(request.state, "correlation_id", None)

    servicio = PipelineEvaluacionService(sesion, almacenamiento)
    return await servicio.ejecutar(
        imagen_frente=contenido_frente,
        content_type_frente=imagen_frente.content_type or "application/octet-stream",
        imagen_reverso=contenido_reverso,
        content_type_reverso=imagen_reverso.content_type or "application/octet-stream",
        submitter_id=usuario.id,
        set_codigo=set_codigo or "",
        acabado=acabado or "",
        correlation_id=str(correlation_id) if correlation_id else None,
    )
