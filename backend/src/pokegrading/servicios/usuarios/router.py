"""Routers HTTP del módulo `usuarios`.

Expone dos routers:
- `router` (prefix `/api/v1/usuarios`): gestión de cuentas (registro).
- `auth_router` (prefix `/api/v1/auth`): operaciones de autenticación (login, refresh).

Rutas en `kebab-case`, prefijo versionado (V6 §3.1).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.datos.db import obtener_sesion
from pokegrading.compartido.schemas.usuarios import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegistroRequest,
    RegistroResponse,
)
from pokegrading.negocio.usuarios.servicio import (
    LoginService,
    RefreshService,
    RegistroService,
)

router = APIRouter(prefix="/api/v1/usuarios", tags=["usuarios"])
auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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
    """Endpoint de registro de cuenta — cubre la US Registrar Cuenta."""
    servicio = RegistroService(sesion)
    return await servicio.ejecutar(datos)


@auth_router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Autenticar y obtener tokens",
)
async def login(
    datos: LoginRequest,
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> LoginResponse:
    """Verifica credenciales y devuelve un par de tokens."""
    servicio = LoginService(sesion)
    return await servicio.ejecutar(datos)


@auth_router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Renovar tokens con un refresh token válido",
    description=(
        "Implementa rotación: cada refresh devuelve un nuevo refresh token, "
        "no el mismo. Esto reduce la ventana de exposición si el token se filtra."
    ),
)
async def refresh(
    datos: RefreshRequest,
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> RefreshResponse:
    """Emite un nuevo par de tokens a partir de un refresh token."""
    servicio = RefreshService(sesion)
    return await servicio.ejecutar(datos)
