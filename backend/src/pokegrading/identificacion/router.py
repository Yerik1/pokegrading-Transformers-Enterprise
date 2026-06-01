"""Router de identificación de cartas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.db import obtener_sesion
from pokegrading.compartido.errores import ErrorValidacion
from pokegrading.identificacion.schemas import BusquedaRapidaResponse
from pokegrading.identificacion.servicio import BusquedaRapidaService
from pokegrading.usuarios.dependencias import requerir_rol
from pokegrading.usuarios.tipos import Rol

router = APIRouter(prefix="/api/v1/identificacion", tags=["identificacion"])

TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024  # 10 MB

requerir_submitter_o_superior = requerir_rol(
    Rol.SUBMITTER, Rol.REVIEWER, Rol.ADMIN, Rol.SUPERADMIN, Rol.B2B_SERVICE_ACCOUNT
)


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

    if len(contenido) == 0:
        raise ErrorValidacion(
            codigo="imagen_vacia",
            mensaje="El archivo de imagen está vacío.",
            campo="imagen_frente",
        )
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise ErrorValidacion(
            codigo="imagen_demasiado_grande",
            mensaje="La imagen excede el tamaño máximo de 10 MB.",
            campo="imagen_frente",
        )

    servicio = BusquedaRapidaService(sesion)
    return await servicio.ejecutar(contenido)
