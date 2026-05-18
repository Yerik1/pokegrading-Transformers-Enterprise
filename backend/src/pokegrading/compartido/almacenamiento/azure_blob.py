"""Implementación contra Azure Blob Storage.

Usa el SDK oficial `azure-storage-blob` en modo async.
La connection string viene de Azure Key Vault en prod (SP8) y del
archivo `.env` en dev.
"""

from __future__ import annotations

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient

from pokegrading.compartido.logging import obtener_logger

logger = obtener_logger(__name__)


class AlmacenamientoAzureBlob:
    """Almacenamiento en Azure Blob Storage.

    Convención de claves del proyecto: `cartas/{card_id}/{frente|reverso}.{ext}`.
    Los contenedores se crean manualmente vía Azure Portal/CLI (no por código)
    para que la creación sea una acción consciente del equipo.
    """

    def __init__(self, connection_string: str) -> None:
        if not connection_string:
            raise ValueError(
                "Azure Storage connection string es requerida. "
                "Configurar AZURE_STORAGE_CONNECTION_STRING en .env."
            )
        self._client = BlobServiceClient.from_connection_string(connection_string)

    async def guardar(
        self,
        contenedor: str,
        clave: str,
        contenido: bytes,
        content_type: str,
    ) -> str:
        """Sube los bytes al blob. Sobrescribe si la clave ya existe."""
        blob_client = self._client.get_blob_client(container=contenedor, blob=clave)
        await blob_client.upload_blob(
            contenido,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        logger.info(
            "almacenamiento_guardado",
            contenedor=contenedor,
            clave=clave,
            tamano_bytes=len(contenido),
        )
        return blob_client.url

    async def obtener_url(self, contenedor: str, clave: str) -> str:
        return self._client.get_blob_client(container=contenedor, blob=clave).url

    async def eliminar(self, contenedor: str, clave: str) -> None:
        blob_client = self._client.get_blob_client(container=contenedor, blob=clave)
        try:
            await blob_client.delete_blob()
            logger.info(
                "almacenamiento_eliminado",
                contenedor=contenedor,
                clave=clave,
            )
        except ResourceNotFoundError:
            # Idempotente: no es error eliminar algo que ya no está.
            pass

    async def existe(self, contenedor: str, clave: str) -> bool:
        blob_client = self._client.get_blob_client(container=contenedor, blob=clave)
        return await blob_client.exists()

    async def cerrar(self) -> None:
        """Cierra la conexión HTTP subyacente. Llamar al shutdown de la app."""
        await self._client.close()
