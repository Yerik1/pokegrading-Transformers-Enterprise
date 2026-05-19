"""Configuración de SQLAlchemy 2 async.

Expone:
- `Base`: clase base declarativa para todos los modelos
- `obtener_sesion`: dependencia FastAPI que entrega una `AsyncSession`
  por request y la cierra al terminar (con rollback en caso de excepción).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from pokegrading.compartido.config import obtener_settings

_settings = obtener_settings()

_engine = create_async_engine(
    _settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

_SessionLocal = async_sessionmaker(
    bind=_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    """Clase base de todos los modelos ORM de PokéGrading."""


async def obtener_sesion() -> AsyncIterator[AsyncSession]:
    """Dependencia FastAPI: provee una `AsyncSession` por request.

    El commit es responsabilidad del servicio de aplicación; aquí solo
    se hace rollback ante excepción no manejada y se cierra la sesión.

    Yields:
        AsyncSession: sesión de SQLAlchemy 2.
    """
    async with _SessionLocal() as sesion:
        try:
            yield sesion
        except Exception:
            await sesion.rollback()
            raise


@asynccontextmanager
async def abrir_sesion() -> AsyncIterator[AsyncSession]:
    """Context manager para usar sesiones fuera de FastAPI (scripts, CLI).

    Misma semántica que `obtener_sesion`: rollback en excepción no manejada
    y cierre garantizado. La diferencia es la forma de uso:

    - `obtener_sesion`: dependencia FastAPI (`Depends(obtener_sesion)`)
    - `abrir_sesion`:   uso directo (`async with abrir_sesion() as sesion:`)

    Yields:
        AsyncSession: sesión de SQLAlchemy 2.
    """
    async with _SessionLocal() as sesion:
        try:
            yield sesion
        except Exception:
            await sesion.rollback()
            raise
