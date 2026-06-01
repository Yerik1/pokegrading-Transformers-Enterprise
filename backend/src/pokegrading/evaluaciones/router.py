"""Router de evaluaciones de cartas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.almacenamiento import obtener_almacenamiento, IAlmacenamientoImagenes
from pokegrading.compartido.db import obtener_sesion
from pokegrading.evaluaciones.schemas import EnviarCartaResponse
from pokegrading.evaluaciones.servicio import EnviarCartaService
from pokegrading.usuarios.dependencias import requerir_rol, usuario_actual
from pokegrading.usuarios.modelos import Usuario
from pokegrading.usuarios.tipos import Rol

router = APIRouter(prefix="/api/v1/evaluaciones", tags=["evaluaciones"])

requerir_submitter_o_superior = requerir_rol(
    Rol.SUBMITTER, Rol.REVIEWER, Rol.ADMIN, Rol.SUPERADMIN, Rol.B2B_SERVICE_ACCOUNT
)


@router.post(
    "/enviar",
    response_model=EnviarCartaResponse,
    status_code=202,
    summary="Enviar carta para evaluación",
    description=(
        "Recibe las imágenes del frente y reverso de una carta, "
        "valida formato, tamaño, polyglot e Image Quality Score, "
        "y registra la solicitud de evaluación. "
        "Retorna un identificador único de evaluación."
    ),
)
async def enviar_carta(
    request: Request,
    imagen_frente: UploadFile = File(..., description="Imagen del frente de la carta"),
    imagen_reverso: UploadFile = File(..., description="Imagen del reverso de la carta"),
    sesion: AsyncSession = Depends(obtener_sesion),
    almacenamiento: IAlmacenamientoImagenes = Depends(obtener_almacenamiento),
    usuario: Usuario = Depends(requerir_submitter_o_superior),
) -> EnviarCartaResponse:
    """Endpoint para enviar carta a evaluación."""
    contenido_frente = await imagen_frente.read()
    contenido_reverso = await imagen_reverso.read()

    correlation_id = getattr(request.state, "correlation_id", None)

    servicio = EnviarCartaService(sesion, almacenamiento)
    return await servicio.ejecutar(
        imagen_frente=contenido_frente,
        content_type_frente=imagen_frente.content_type or "application/octet-stream",
        imagen_reverso=contenido_reverso,
        content_type_reverso=imagen_reverso.content_type or "application/octet-stream",
        submitter_id=usuario.id,
        correlation_id=str(correlation_id) if correlation_id else None,
    )
