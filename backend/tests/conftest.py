"""Fixtures compartidos de pytest."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pokegrading.compartido.db import Base, obtener_sesion
from pokegrading.main import app


@pytest.fixture(scope="session")
async def _engine():
    """Engine SQLite async en memoria, válido para tests unitarios.

    NOTA: los tipos `postgresql.UUID` y `sa.Enum` con `name=` funcionan
    en SQLite gracias a la compatibilidad de SQLAlchemy 2.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def _sesion(_engine) -> AsyncIterator[AsyncSession]:
    session_local = async_sessionmaker(bind=_engine, expire_on_commit=False)
    async with session_local() as sesion:
        yield sesion
        await sesion.rollback()


@pytest.fixture
async def cliente(_sesion: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Cliente HTTPX asíncrono contra la app FastAPI con BD de prueba."""

    async def _override():
        yield _sesion

    app.dependency_overrides[obtener_sesion] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
