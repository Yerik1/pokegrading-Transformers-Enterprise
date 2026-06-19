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


@asynccontextmanager
async def unidad_de_trabajo(sesion: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Unidad de trabajo explícita: agrupa una o más escrituras en una
    única transacción atómica.

    Diseñada para servicios de aplicación que ejecutan múltiples
    operaciones de escritura que deben confirmarse o revertirse como
    una sola unidad (ej. B2B: registrar auditoría + incrementar rate
    limit; Catálogo: guardar carta + limpiar blobs en caso de fallo).

    A diferencia de depender únicamente del rollback implícito de
    `obtener_sesion` ante una excepción no capturada, este context
    manager hace explícito en el código de cada servicio dónde
    empieza y termina la transacción, sin duplicar el bloque
    try/except/commit/rollback en cada uno.

    Uso:
        async def ejecutar(self, ...):
            ...
            async with unidad_de_trabajo(self._sesion):
                await self._repo.registrar_consulta(...)
                await self._repo.incrementar_cartas_consultadas(...)
            # commit ya ocurrió aquí si no hubo excepción

    Si el bloque lanza cualquier excepción (incluyendo `IntegrityError`),
    se hace rollback y la excepción se re-lanza sin modificar para que
    el servicio decida cómo traducirla a un error de dominio.

    Args:
        sesion: la `AsyncSession` activa del request o script en curso.

    Yields:
        La misma sesión recibida, para encadenar repositorios dentro
        del bloque `async with`.
    """
    try:
        yield sesion
        await sesion.commit()
    except Exception:
        await sesion.rollback()
        raise