"""Router de identificación de cartas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.dependencias import requerir_submitter_o_superior
from pokegrading.compartido.schemas.identificacion import BusquedaRapidaResponse
from pokegrading.datos.db import obtener_sesion
from pokegrading.negocio.identificacion.servicio import BusquedaRapidaService

router = APIRouter(prefix="/api/v1/identificacion", tags=["identificacion"])


@router.post(
    "/busqueda-rapida",
    response_model=BusquedaRapidaResponse,
    summary="Búsqueda rápida de carta por imagen",
    description=(
        "Identifica una carta a partir de su imagen usando hash perceptual. "
        "Devuelve los 3 mejores candidatos con su nivel de confianza. "
        "Si el candidato top supera el umbral configurado, se acepta automáticamente."
    ),
)
async def busqueda_rapida(
    imagen_frente: UploadFile = File(..., description="Imagen del frente de la carta"),
    sesion: AsyncSession = Depends(obtener_sesion),
    _usuario=Depends(requerir_submitter_o_superior),
) -> BusquedaRapidaResponse:
    """Endpoint de búsqueda rápida de carta por phash."""
    contenido = await imagen_frente.read()
    servicio = BusquedaRapidaService(sesion)
    return await servicio.ejecutar(contenido)
