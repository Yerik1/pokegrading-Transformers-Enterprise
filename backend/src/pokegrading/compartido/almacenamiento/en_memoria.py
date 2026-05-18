"""Implementación en memoria del almacenamiento.

**Solo para tests.** NO usar en producción ni dev: los datos se pierden
al recargar el proceso. Pasa la suite de tests del contrato igual que
`AlmacenamientoAzureBlob`, garantizando equivalencia de comportamiento.
"""

from __future__ import annotations


class AlmacenamientoEnMemoria:
    """Almacenamiento en memoria — un dict bajo el capó."""

    def __init__(self) -> None:
        # Estructura: {contenedor: {clave: (bytes, content_type)}}
        self._datos: dict[str, dict[str, tuple[bytes, str]]] = {}

    async def guardar(
        self,
        contenedor: str,
        clave: str,
        contenido: bytes,
        content_type: str,
    ) -> str:
        self._datos.setdefault(contenedor, {})[clave] = (contenido, content_type)
        return await self.obtener_url(contenedor, clave)

    async def obtener_url(self, contenedor: str, clave: str) -> str:
        return f"memory://{contenedor}/{clave}"

    async def eliminar(self, contenedor: str, clave: str) -> None:
        self._datos.get(contenedor, {}).pop(clave, None)

    async def existe(self, contenedor: str, clave: str) -> bool:
        return clave in self._datos.get(contenedor, {})

    # --- Métodos auxiliares solo para tests ---

    def leer_contenido(self, contenedor: str, clave: str) -> bytes | None:
        """Solo para tests: lee los bytes guardados para asserts."""
        data = self._datos.get(contenedor, {}).get(clave)
        return data[0] if data else None

    def leer_content_type(self, contenedor: str, clave: str) -> str | None:
        """Solo para tests: lee el content_type guardado."""
        data = self._datos.get(contenedor, {}).get(clave)
        return data[1] if data else None
