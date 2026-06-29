"""Interfaz abstracta de almacenamiento de objetos (DA-11, R8).

Las claves se organizan jerárquicamente con `/` como separador
(ejemplo: `cartas/{card_id}/frente.jpg`).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pokegrading.compartido.config import obtener_settings


@runtime_checkable
class IAlmacenamientoImagenes(Protocol):
    """Contrato para almacenamiento de imágenes binarias."""

    async def guardar(
        self,
        contenedor: str,
        clave: str,
        contenido: bytes,
        content_type: str,
    ) -> str:
        """Persiste los bytes y devuelve la URL absoluta de acceso.

        Si la clave ya existe, se sobrescribe (semántica idempotente
        para reintentos).

        Args:
            contenedor: nombre del contenedor (ej. `cartas-referencia`).
            clave: ruta lógica dentro del contenedor (ej. `cartas/abc/frente.jpg`).
            contenido: bytes a persistir.
            content_type: MIME type (ej. `image/jpeg`).

        Returns:
            URL absoluta del recurso.
        """
        ...

    async def obtener_url(self, contenedor: str, clave: str) -> str:
        """Devuelve la URL absoluta del recurso (no verifica que exista)."""
        ...

    async def descargar(self, contenedor: str, clave: str) -> bytes:
        """Descarga y devuelve los bytes del recurso.

        Usado por el pipeline de preprocesamiento (Sprint 4, US 191)
        para recuperar las imágenes originales subidas por
        `EnviarCartaService` y procesarlas.

        Raises:
            ErrorNoEncontrado: si la clave no existe en el contenedor.
        """
        ...

    async def eliminar(self, contenedor: str, clave: str) -> None:
        """Elimina el recurso. Idempotente: no falla si no existe."""
        ...

    async def existe(self, contenedor: str, clave: str) -> bool:
        """Verifica si el recurso existe en el almacenamiento."""
        ...


def obtener_almacenamiento() -> IAlmacenamientoImagenes:
    """Dependencia FastAPI: provee la implementación configurada.

    Construye `AlmacenamientoAzureBlob` usando la connection string del
    config. En tests, esta dependencia se sobrescribe con
    `AlmacenamientoEnMemoria` vía `app.dependency_overrides`.
    """
    # Import local para no cargar el SDK de Azure cuando los tests
    # overridean esta dependencia.
    from pokegrading.compartido.almacenamiento.azure_blob import (
        AlmacenamientoAzureBlob,
    )

    settings = obtener_settings()
    return AlmacenamientoAzureBlob(settings.azure_storage_connection_string)


# compartido/almacenamiento/base.py
async def eliminar_blob_silencioso(
    almacenamiento: IAlmacenamientoImagenes,
    contenedor: str,
    clave: str,
    logger: Any,
) -> None:
    try:
        await almacenamiento.eliminar(contenedor, clave)
    except Exception:
        logger.warning("blob_huerfano_no_eliminado", contenedor=contenedor, clave=clave)


# Mapeo MIME -> extensión para nombrar blobs de forma consistente.
# Centralizado aquí para reutilizar en cualquier módulo que suba imágenes.
EXTENSION_POR_MIME: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
}
