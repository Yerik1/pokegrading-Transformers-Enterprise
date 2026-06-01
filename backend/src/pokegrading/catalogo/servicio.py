"""Servicio de aplicación: agregar carta al catálogo.

Orquesta:
1. Validación de imágenes (reglas)
2. Verificación de duplicados por identity tuple (repositorio)
3. Upload a Blob Storage (almacenamiento)
4. Persistencia en BD (repositorio + commit)
5. Rollback compensatorio si algo falla a mitad: BD se rollbackea y los
   blobs subidos se eliminan para no dejar huérfanos.
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.catalogo import reglas
from pokegrading.catalogo.modelos import Carta
from pokegrading.catalogo.repositorio import CartaRepositorio
from pokegrading.catalogo.schemas import CartaResponse, CrearCartaRequest
from pokegrading.compartido.almacenamiento import IAlmacenamientoImagenes
from pokegrading.identificacion.algoritmo import calcular_phash
from pokegrading.compartido.config import obtener_settings
from pokegrading.compartido.errores import ErrorConflicto
from pokegrading.compartido.logging import obtener_logger

logger = obtener_logger(__name__)

# Mapeo MIME -> extensión para nombrar los blobs de forma consistente
_EXTENSION_POR_MIME: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
}


class CrearCartaService:
    """Caso de uso: dar de alta una carta nueva en el catálogo."""

    def __init__(
        self,
        sesion: AsyncSession,
        almacenamiento: IAlmacenamientoImagenes,
    ) -> None:
        self._sesion = sesion
        self._repo = CartaRepositorio(sesion)
        self._almacenamiento = almacenamiento

    async def ejecutar(
        self,
        datos: CrearCartaRequest,
        *,
        imagen_frente: bytes,
        content_type_frente: str,
        imagen_reverso: bytes | None,
        content_type_reverso: str | None,
        creada_por_id: uuid.UUID,
    ) -> CartaResponse:
        # === 1. Validar imágenes ===
        mime_frente = reglas.validar_imagen(
            imagen_frente,
            content_type_cliente=content_type_frente,
            campo="imagen_frente",
        )
        mime_reverso: str | None = None
        if imagen_reverso is not None:
            mime_reverso = reglas.validar_imagen(
                imagen_reverso,
                content_type_cliente=content_type_reverso or "application/octet-stream",
                campo="imagen_reverso",
            )

        # === 1b. Calcular phash del frente para búsqueda rápida ===
        try:
            phash_frente = calcular_phash(imagen_frente)
        except Exception:
            phash_frente = None

        # === 2. Verificar duplicado por identity tuple ===
        existente = await self._repo.obtener_por_identity_tuple(
            set_codigo=datos.set_codigo,
            numero=datos.numero,
            edicion=datos.edicion,
            idioma=datos.idioma,
            acabado=datos.acabado,
        )
        if existente is not None:
            raise ErrorConflicto(
                codigo="carta_duplicada",
                mensaje=(
                    f"Ya existe una carta con la misma identidad: "
                    f"{datos.set_codigo} {datos.numero} "
                    f"({datos.edicion.value}, {datos.idioma.value}, "
                    f"{datos.acabado.value})."
                ),
                campo="set_codigo",
            )

        # === 3. Generar IDs y subir imágenes ===
        carta_id = uuid.uuid4()
        contenedor = obtener_settings().azure_blob_container_cartas

        clave_frente = f"cartas/{carta_id}/frente.{_EXTENSION_POR_MIME[mime_frente]}"
        clave_reverso: str | None = None
        if mime_reverso is not None:
            clave_reverso = (
                f"cartas/{carta_id}/reverso.{_EXTENSION_POR_MIME[mime_reverso]}"
            )

        # Sube frente primero; si falla, no hay nada que limpiar.
        url_frente = await self._almacenamiento.guardar(
            contenedor, clave_frente, imagen_frente, mime_frente
        )

        url_reverso: str | None = None
        if imagen_reverso is not None and clave_reverso is not None and mime_reverso:
            try:
                url_reverso = await self._almacenamiento.guardar(
                    contenedor, clave_reverso, imagen_reverso, mime_reverso
                )
            except Exception:
                # Limpieza compensatoria: borramos el frente que ya subimos
                # antes de propagar la excepción.
                await self._eliminar_blob_silencioso(contenedor, clave_frente)
                raise

        # === 4. Persistir en BD ===
        nueva = Carta(
            id=carta_id,
            set_codigo=datos.set_codigo,
            numero=datos.numero,
            edicion=datos.edicion,
            idioma=datos.idioma,
            acabado=datos.acabado,
            nombre=datos.nombre,
            rareza=datos.rareza,
            tipo=datos.tipo,
            hp=datos.hp,
            ilustrador=datos.ilustrador,
            anio_impresion=datos.anio_impresion,
            url_imagen_frente=url_frente,
            clave_blob_frente=clave_frente,
            url_imagen_reverso=url_reverso,
            clave_blob_reverso=clave_reverso,
            creada_por_id=creada_por_id,
            phash_frente=phash_frente,
        )

        try:
            await self._repo.guardar(nueva)
            await self._sesion.commit()
        except IntegrityError as exc:
            # Race condition: otro request creó la misma identity tuple
            # entre nuestra verificación y el insert. Rollback BD + limpiar blobs.
            await self._sesion.rollback()
            await self._eliminar_blob_silencioso(contenedor, clave_frente)
            if clave_reverso is not None:
                await self._eliminar_blob_silencioso(contenedor, clave_reverso)
            raise ErrorConflicto(
                codigo="carta_duplicada",
                mensaje="Ya existe una carta con la misma identidad.",
                campo="set_codigo",
            ) from exc

        logger.info(
            "carta_creada",
            carta_id=str(nueva.id),
            set_codigo=nueva.set_codigo,
            numero=nueva.numero,
            edicion=nueva.edicion.value,
            idioma=nueva.idioma.value,
            acabado=nueva.acabado.value,
            creada_por_id=str(creada_por_id),
        )

        return CartaResponse.model_validate(nueva)

    async def _eliminar_blob_silencioso(self, contenedor: str, clave: str) -> None:
        """Intenta eliminar un blob para limpieza compensatoria.

        Si la eliminación falla (red caída, etc.), se loguea pero no se
        propaga: el rollback del BD es lo prioritario. Los blobs huérfanos
        que queden se limpian con un job de mantenimiento periódico.
        """
        try:
            await self._almacenamiento.eliminar(contenedor, clave)
        except Exception:
            logger.warning(
                "blob_huerfano_no_eliminado",
                contenedor=contenedor,
                clave=clave,
            )
