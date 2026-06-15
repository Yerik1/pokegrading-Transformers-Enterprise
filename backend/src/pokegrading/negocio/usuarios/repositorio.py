"""Repositorio del agregado `Usuario` (acceso a datos).

El repositorio aísla SQLAlchemy del servicio de aplicación. El servicio
trabaja con métodos semánticos (`obtener_por_correo`, `guardar`) y no
sabe que detrás hay SQL.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.negocio.usuarios.modelos import Usuario


class UsuarioRepositorio:
    """Acceso a la tabla `usuarios`."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_por_correo(self, correo: str) -> Usuario | None:
        """Busca un usuario por correo (case-insensitive)."""
        normalizado = correo.strip().lower()
        stmt = select(Usuario).where(Usuario.correo == normalizado)
        resultado = await self._sesion.execute(stmt)
        return resultado.scalar_one_or_none()

    async def obtener_por_id(self, usuario_id: uuid.UUID) -> Usuario | None:
        """Busca un usuario por id."""
        return await self._sesion.get(Usuario, usuario_id)

    async def guardar(self, usuario: Usuario) -> Usuario:
        """Persiste un usuario nuevo o actualiza uno existente.

        El commit se delega al servicio (para mantener atomicidad por
        unidad de trabajo).
        """
        self._sesion.add(usuario)
        await self._sesion.flush()
        return usuario
