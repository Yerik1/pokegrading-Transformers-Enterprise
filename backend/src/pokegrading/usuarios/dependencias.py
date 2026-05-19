"""Dependencias FastAPI relacionadas con autenticación y autorización (SP1).

Pendiente de uso por endpoints autenticados en próximas US. Se deja
preparado para que el siguiente módulo (catálogo) solo importe
`requerir_admin` o `usuario_actual`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.db import obtener_sesion
from pokegrading.compartido.errores import ErrorAutenticacion, ErrorAutorizacion
from pokegrading.compartido.seguridad import decodificar_token
from pokegrading.usuarios.modelos import Usuario
from pokegrading.usuarios.repositorio import UsuarioRepositorio
from pokegrading.usuarios.tipos import Rol

_bearer = HTTPBearer(auto_error=False)


async def usuario_actual(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> Usuario:
    """Resuelve el usuario autenticado a partir del JWT en `Authorization: Bearer`.

    Raises:
        ErrorAutenticacion: si no hay token, está expirado o el sub
            no corresponde a un usuario existente.
    """
    if credenciales is None:
        raise ErrorAutenticacion(
            codigo="token_faltante",
            mensaje="Se requiere autenticación.",
        )

    payload = decodificar_token(credenciales.credentials)
    if payload.get("tipo") != "access":
        raise ErrorAutenticacion(
            codigo="tipo_token_invalido",
            mensaje="Se esperaba un access token.",
        )

    sub = payload.get("sub")
    if not sub:
        raise ErrorAutenticacion(
            codigo="token_invalido",
            mensaje="El token no contiene un sujeto válido.",
        )

    try:
        usuario_id = uuid.UUID(sub)
    except ValueError as exc:
        raise ErrorAutenticacion(
            codigo="token_invalido",
            mensaje="El identificador del usuario es inválido.",
        ) from exc

    repo = UsuarioRepositorio(sesion)
    usuario = await repo.obtener_por_id(usuario_id)
    if usuario is None:
        raise ErrorAutenticacion(
            codigo="usuario_no_existe",
            mensaje="El usuario asociado al token ya no existe.",
        )
    return usuario


def requerir_rol(*roles: Rol):
    """Factory de dependencia que exige que el usuario tenga uno de los roles dados.

    Uso:
        ```python
        @router.post("/cartas", dependencies=[Depends(requerir_rol(Rol.ADMIN))])
        async def agregar_carta(...): ...
        ```
    """
    permitidos = set(roles)

    async def _verificador(
        usuario: Annotated[Usuario, Depends(usuario_actual)],
    ) -> Usuario:
        if usuario.rol not in permitidos:
            raise ErrorAutorizacion(
                codigo="rol_insuficiente",
                mensaje="No tienes permiso para realizar esta acción.",
                contexto={
                    "rol_actual": usuario.rol.value,
                    "roles_permitidos": [r.value for r in permitidos],
                },
            )
        return usuario

    return _verificador


# Alias conveniente: la mayoría de endpoints "admin-only" aceptan ambos roles.
# Uso: `Depends(requerir_admin_o_superadmin)`
requerir_admin_o_superadmin = requerir_rol(Rol.ADMIN, Rol.SUPERADMIN)
