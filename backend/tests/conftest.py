"""Fixtures compartidos de pytest.

Cada test recibe una BD SQLite en memoria fresca + un almacenamiento
en memoria. Sin esto, los `commit()` del código persisten datos entre
tests y se rompe el aislamiento.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from pokegrading.compartido.almacenamiento import (
    AlmacenamientoEnMemoria,
    obtener_almacenamiento,
)
from pokegrading.compartido.db import Base, obtener_sesion
from pokegrading.main import app


@pytest.fixture
async def _engine():
    """Engine SQLite async en memoria — uno nuevo por test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def _sesion(_engine) -> AsyncIterator[AsyncSession]:
    """Sesión SQLAlchemy bound al engine de prueba del test actual."""
    session_local = async_sessionmaker(bind=_engine, expire_on_commit=False)
    async with session_local() as sesion:
        yield sesion


@pytest.fixture
def _almacenamiento() -> AlmacenamientoEnMemoria:
    """Almacenamiento en memoria — uno nuevo por test."""
    return AlmacenamientoEnMemoria()


@pytest.fixture
async def cliente(
    _sesion: AsyncSession,
    _almacenamiento: AlmacenamientoEnMemoria,
) -> AsyncIterator[AsyncClient]:
    """Cliente HTTPX async con BD + almacenamiento de prueba inyectados."""

    async def _override_sesion():
        yield _sesion

    def _override_almacenamiento():
        return _almacenamiento

    app.dependency_overrides[obtener_sesion] = _override_sesion
    app.dependency_overrides[obtener_almacenamiento] = _override_almacenamiento
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()