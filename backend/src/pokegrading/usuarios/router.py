"""Router HTTP del módulo `usuarios`.

Rutas en `kebab-case`, prefijo versionado `/api/v1/usuarios` (V6 §3.1).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.db import obtener_sesion
from pokegrading.usuarios.schemas import RegistroRequest, RegistroResponse
from pokegrading.usuarios.servicio import RegistroService

router = APIRouter(prefix="/api/v1/usuarios", tags=["usuarios"])


@router.post(
    "/registro",
    response_model=RegistroResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una cuenta nueva (Submitter)",
    description=(
        "Crea una cuenta de Submitter activa de inmediato (sin verificación "
        "por correo). Devuelve el usuario creado y un par de tokens "
        "(access + refresh) para autenticar requests subsecuentes."
    ),
)
async def registrar_cuenta(
    datos: RegistroRequest,
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> RegistroResponse:
    """Endpoint de registro de cuenta.

    Cubre la US "Registrar cuenta" del Sprint 1.

    Args:
        datos: payload validado por Pydantic.
        sesion: sesión de BD inyectada por FastAPI.

    Returns:
        Usuario público y par de tokens iniciales.
    """
    servicio = RegistroService(sesion)
    return await servicio.ejecutar(datos)
