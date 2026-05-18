"""Configuración de Alembic.

Alembic corre síncrono (mejor para migraciones), aunque la app use asyncpg.
Convertimos el DSN de asyncpg a psycopg si hace falta. Para mantener simple
el setup en MVP, se asume que el equipo tiene `psycopg2-binary` o el driver
síncrono por defecto disponible vía `psycopg` (incluido transitivamente).
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from pokegrading.compartido.config import obtener_settings
from pokegrading.compartido.db import Base

# importar modelos para que estén registrados en Base.metadata
from pokegrading.usuarios import modelos  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inyectamos el DSN de runtime, convirtiéndolo a versión sync para Alembic
_settings = obtener_settings()
_sync_url = _settings.database_url.replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", _sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo offline (genera SQL sin conectar a la BD)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones contra la BD configurada."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
