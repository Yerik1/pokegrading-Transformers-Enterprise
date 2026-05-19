"""Configuración centralizada de la aplicación.

Toda la configuración se inyecta vía variables de entorno (SP8). En `prod`
los valores sensibles vienen de Azure Key Vault (claves `kebab-case`,
ej. `pokegrading-jwt-secret`). En dev, vienen del archivo `.env` ubicado
en la raíz del repo.

No leer variables de entorno fuera de este módulo.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raíz del repo: este archivo está en backend/src/pokegrading/compartido/config.py
# parents[0]=compartido, [1]=pokegrading, [2]=src, [3]=backend, [4]=raíz del repo
_RAIZ_REPO = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Configuración tipada de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=_RAIZ_REPO / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["dev", "prod"] = "dev"

    database_url: str = Field(
        ...,
        description="DSN asyncpg de PostgreSQL",
        examples=[
            "postgresql+asyncpg://pokegrading:pokegrading@localhost:5432/pokegrading_dev"
        ],
    )

    jwt_secret_key: str = Field(..., min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 7

    # Azure Blob Storage (Fase 1B)
    # Connection string del Storage Account `stpokegradingdev`.
    # Obtenerla del Portal: Storage Account → Access keys → key1 → Connection string.
    # NUNCA commitear este valor — usar Key Vault en prod (SP8).
    azure_storage_connection_string: str = Field(
        ...,
        description="Connection string de Azure Storage para acceso a Blob.",
    )
    azure_blob_container_cartas: str = Field(
        default="cartas-referencia",
        description="Nombre del contenedor para imágenes de catálogo de cartas.",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    disclosure_version: str = "v1.0"


@lru_cache(maxsize=1)
def obtener_settings() -> Settings:
    """Carga y cachea las settings.

    Se cachea con `lru_cache` para evitar leer el `.env` en cada inyección
    de FastAPI. La cache se invalida en tests recreando la app.

    Returns:
        Settings: instancia única para todo el proceso.
    """
    return Settings()  # type: ignore[call-arg]
