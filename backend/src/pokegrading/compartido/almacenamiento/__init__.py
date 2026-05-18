"""Módulo de almacenamiento de objetos (imágenes de cartas, etc.).

Expone una interfaz abstracta `IAlmacenamientoImagenes` con dos
implementaciones:
- `AlmacenamientoAzureBlob`: la usada en dev/prod, contra Azure Blob Storage.
- `AlmacenamientoEnMemoria`: para tests unitarios sin Azure.

El dominio (cartas, evaluaciones) depende solamente de la interfaz —
nunca de una implementación concreta. Esto permite hacer swap de
proveedor (Azure Blob → S3 → GCS) sin tocar el código de negocio.
"""

from pokegrading.compartido.almacenamiento.azure_blob import AlmacenamientoAzureBlob
from pokegrading.compartido.almacenamiento.base import (
    IAlmacenamientoImagenes,
    obtener_almacenamiento,
)
from pokegrading.compartido.almacenamiento.en_memoria import AlmacenamientoEnMemoria

__all__ = [
    "AlmacenamientoAzureBlob",
    "AlmacenamientoEnMemoria",
    "IAlmacenamientoImagenes",
    "obtener_almacenamiento",
]
