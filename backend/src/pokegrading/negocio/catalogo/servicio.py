"""Servicio de aplicación: agregar carta al catálogo.

El método `ejecutar()` orquesta 4 pasos, cada uno extraído a su propio
método privado para que el flujo principal se lea como una lista de
pasos de alto nivel:

1. `_validar_y_preparar_imagenes` — formato/tamaño + phash para búsqueda
2. `_verificar_no_duplicada`      — identity tuple única en el catálogo
3. `_subir_imagenes`              — sube a Blob Storage, con limpieza
                                     compensatoria si la segunda falla
4. `_persistir_carta`             — guarda en BD como unidad de trabajo
                                     atómica, con limpieza compensatoria
                                     de blobs si hay conflicto de duplicado
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.almacenamiento import IAlmacenamientoImagenes
from pokegrading.compartido.almacenamiento.base import (
    EXTENSION_POR_MIME,
    eliminar_blob_silencioso,
)
from pokegrading.compartido.config import obtener_settings
from pokegrading.compartido.errores import ErrorConflicto
from pokegrading.compartido.imagenes import validar_imagen
from pokegrading.compartido.logging import obtener_logger
from pokegrading.compartido.schemas.catalogo import CartaResponse, CrearCartaRequest
from pokegrading.datos.db import unidad_de_trabajo
from pokegrading.negocio.catalogo.modelos import Carta
from pokegrading.negocio.catalogo.repositorio import CartaRepositorio
from pokegrading.negocio.identificacion.algoritmo import calcular_phash

logger = obtener_logger(__name__)


class _ImagenesPreparadas:
    """Resultado del paso 1: MIME detectado + phash del frente."""

    __slots__ = ("mime_frente", "mime_reverso", "phash_frente")

    def __init__(
        self, mime_frente: str, mime_reverso: str | None, phash_frente: str | None
    ) -> None:
        self.mime_frente = mime_frente
        self.mime_reverso = mime_reverso
        self.phash_frente = phash_frente


class _ImagenesSubidas:
    """Resultado del paso 3: URLs y claves de blob de ambas imágenes."""

    __slots__ = ("contenedor", "url_frente", "clave_frente", "url_reverso", "clave_reverso")

    def __init__(
        self,
        contenedor: str,
        url_frente: str,
        clave_frente: str,
        url_reverso: str | None,
        clave_reverso: str | None,
    ) -> None:
        self.contenedor = contenedor
        self.url_frente = url_frente
        self.clave_frente = clave_frente
        self.url_reverso = url_reverso
        self.clave_reverso = clave_reverso


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

    # ------------------------------------------------------------------
    # Orquestador — un paso por línea, sin lógica de negocio inline
    # ------------------------------------------------------------------

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
        imagenes = self._validar_y_preparar_imagenes(
            imagen_frente, content_type_frente, imagen_reverso, content_type_reverso
        )

        await self._verificar_no_duplicada(datos)

        carta_id = uuid.uuid4()
        subidas = await self._subir_imagenes(
            carta_id, imagen_frente, imagenes.mime_frente,
            imagen_reverso, imagenes.mime_reverso,
        )

        nueva = await self._persistir_carta(
            carta_id, datos, creada_por_id, imagenes, subidas
        )

        return CartaResponse.model_validate(nueva)

    # ------------------------------------------------------------------
    # Paso 1: validar imágenes + calcular phash para búsqueda rápida
    # ------------------------------------------------------------------

    @staticmethod
    def _validar_y_preparar_imagenes(
        imagen_frente: bytes,
        content_type_frente: str,
        imagen_reverso: bytes | None,
        content_type_reverso: str | None,
    ) -> _ImagenesPreparadas:
        """Valida formato/tamaño de ambas imágenes y calcula el phash
        del frente para alimentar la búsqueda rápida por imagen.

        Raises:
            ErrorValidacion: si alguna imagen no cumple formato/tamaño.
        """
        mime_frente = validar_imagen(
            imagen_frente,
            content_type_cliente=content_type_frente,
            campo="imagen_frente",
        )

        mime_reverso: str | None = None
        if imagen_reverso is not None:
            mime_reverso = validar_imagen(
                imagen_reverso,
                content_type_cliente=content_type_reverso or "application/octet-stream",
                campo="imagen_reverso",
            )

        try:
            phash_frente = calcular_phash(imagen_frente)
        except Exception:
            # El phash es una optimización de búsqueda, no un requisito
            # de la carta: si falla, la carta igual se crea sin él.
            phash_frente = None

        return _ImagenesPreparadas(mime_frente, mime_reverso, phash_frente)

    # ------------------------------------------------------------------
    # Paso 2: verificar que la identity tuple no exista ya
    # ------------------------------------------------------------------

    async def _verificar_no_duplicada(self, datos: CrearCartaRequest) -> None:
        """Verifica que no exista ya una carta con la misma identity tuple.

        Esta es una verificación optimista: la garantía real de unicidad
        la da la restricción UNIQUE de BD, manejada como IntegrityError
        en `_persistir_carta` para cubrir la race condition entre esta
        verificación y el insert.

        Raises:
            ErrorConflicto: si ya existe una carta con la misma identidad.
        """
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

    # ------------------------------------------------------------------
    # Paso 3: subir imágenes a Blob Storage (con limpieza compensatoria)
    # ------------------------------------------------------------------

    async def _subir_imagenes(
        self,
        carta_id: uuid.UUID,
        imagen_frente: bytes,
        mime_frente: str,
        imagen_reverso: bytes | None,
        mime_reverso: str | None,
    ) -> _ImagenesSubidas:
        """Sube frente y, si existe, reverso a Blob Storage.

        Si la subida del reverso falla después de que el frente ya se
        subió, el frente se elimina para no dejar un blob huérfano.
        """
        contenedor = obtener_settings().azure_blob_container_cartas
        clave_frente = f"cartas/{carta_id}/frente.{EXTENSION_POR_MIME[mime_frente]}"

        try:
            url_frente = await self._almacenamiento.guardar(
                contenedor, clave_frente, imagen_frente, mime_frente
            )
        except Exception as exc:
            logger.error(
                "error_subiendo_imagen_frente",
                carta_id=str(carta_id),
                clave=clave_frente,
            )
            raise exc

        clave_reverso: str | None = None
        url_reverso: str | None = None
        if imagen_reverso is not None and mime_reverso is not None:
            clave_reverso = f"cartas/{carta_id}/reverso.{EXTENSION_POR_MIME[mime_reverso]}"
            try:
                url_reverso = await self._almacenamiento.guardar(
                    contenedor, clave_reverso, imagen_reverso, mime_reverso
                )
            except Exception:
                await eliminar_blob_silencioso(contenedor, clave_frente, logger)
                raise

        return _ImagenesSubidas(contenedor, url_frente, clave_frente, url_reverso, clave_reverso)

    # ------------------------------------------------------------------
    # Paso 4: persistir en BD como unidad de trabajo atómica
    # ------------------------------------------------------------------

    async def _persistir_carta(
        self,
        carta_id: uuid.UUID,
        datos: CrearCartaRequest,
        creada_por_id: uuid.UUID,
        imagenes: _ImagenesPreparadas,
        subidas: _ImagenesSubidas,
    ) -> Carta:
        """Crea y guarda el registro de carta.

        Si la escritura en BD falla por una identity tuple duplicada
        (race condition entre `_verificar_no_duplicada` y este insert),
        los blobs ya subidos a Azure se limpian antes de propagar el
        error de dominio.
        """
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
            url_imagen_frente=subidas.url_frente,
            clave_blob_frente=subidas.clave_frente,
            url_imagen_reverso=subidas.url_reverso,
            clave_blob_reverso=subidas.clave_reverso,
            creada_por_id=creada_por_id,
            phash_frente=imagenes.phash_frente,
        )

        try:
            async with unidad_de_trabajo(self._sesion):
                await self._repo.guardar(nueva)
        except IntegrityError as exc:
            await eliminar_blob_silencioso(subidas.contenedor, subidas.clave_frente, logger)
            if subidas.clave_reverso is not None:
                await eliminar_blob_silencioso(subidas.contenedor, subidas.clave_reverso, logger)
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

        return nueva