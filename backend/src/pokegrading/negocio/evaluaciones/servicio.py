"""Servicio de aplicación: enviar carta para evaluación.

El método `ejecutar()` orquesta 5 pasos, cada uno extraído a su propio
método privado para que el flujo principal se lea como una lista de
pasos de alto nivel:

1. `_validar_imagenes`     — formato, tamaño y polyglot rejection
2. `_calcular_calidad`     — Image Quality Score, con umbral mínimo
3. `_evaluar_saturacion`   — cola de evaluaciones pendientes
4. `_subir_imagenes`       — sube a Blob Storage, con limpieza compensatoria
5. `_persistir_evaluacion` — guarda en BD como unidad de trabajo atómica
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido import imagenes as reglas_imagen
from pokegrading.compartido.almacenamiento import IAlmacenamientoImagenes
from pokegrading.compartido.almacenamiento.base import (
    EXTENSION_POR_MIME,
    eliminar_blob_silencioso,
)
from pokegrading.compartido.errores import ErrorValidacion
from pokegrading.compartido.logging import obtener_logger
from pokegrading.compartido.schemas.evaluaciones import EnviarCartaResponse
from pokegrading.datos.db import unidad_de_trabajo
from pokegrading.negocio.evaluaciones.modelos import Evaluacion
from pokegrading.negocio.evaluaciones.reglas import (
    UMBRAL_IQS_DEFAULT,
    calcular_iq_score,
)
from pokegrading.negocio.evaluaciones.repositorio import EvaluacionRepositorio

logger = obtener_logger(__name__)

UMBRAL_SATURACION = 50
TIEMPO_ESTIMADO_SATURACION_SEGUNDOS = 120
CONTENEDOR_EVALUACIONES = "cartas-referencia"


def _generar_identificador(evaluacion_id: uuid.UUID) -> str:
    """Genera identificador legible tipo EV-2026-05-31-A1B3."""
    hoy = datetime.now(UTC).strftime("%Y-%m-%d")
    sufijo = str(evaluacion_id).upper().replace("-", "")[:4]
    return f"EV-{hoy}-{sufijo}"


class _ImagenesValidadas:
    """Resultado del paso 1: bytes ya validados + su MIME detectado."""

    __slots__ = ("mime_frente", "mime_reverso")

    def __init__(self, mime_frente: str, mime_reverso: str) -> None:
        self.mime_frente = mime_frente
        self.mime_reverso = mime_reverso


class _CalidadImagen:
    """Resultado del paso 2: scores de calidad de ambas imágenes."""

    __slots__ = ("iq_frente", "iq_reverso")

    def __init__(self, iq_frente: float, iq_reverso: float) -> None:
        self.iq_frente = iq_frente
        self.iq_reverso = iq_reverso


class _ImagenesSubidas:
    """Resultado del paso 4: URLs y claves de blob de ambas imágenes."""

    __slots__ = ("url_frente", "clave_frente", "url_reverso", "clave_reverso")

    def __init__(
        self, url_frente: str, clave_frente: str, url_reverso: str, clave_reverso: str
    ) -> None:
        self.url_frente = url_frente
        self.clave_frente = clave_frente
        self.url_reverso = url_reverso
        self.clave_reverso = clave_reverso


class EnviarCartaService:
    """Caso de uso: enviar carta para evaluación."""

    def __init__(
        self,
        sesion: AsyncSession,
        almacenamiento: IAlmacenamientoImagenes,
    ) -> None:
        self._sesion = sesion
        self._repo = EvaluacionRepositorio(sesion)
        self._almacenamiento = almacenamiento

    # ------------------------------------------------------------------
    # Orquestador — un paso por línea, sin lógica de negocio inline
    # ------------------------------------------------------------------

    async def ejecutar(
        self,
        imagen_frente: bytes,
        content_type_frente: str,
        imagen_reverso: bytes,
        content_type_reverso: str,
        submitter_id: uuid.UUID,
        correlation_id: str | None = None,
    ) -> EnviarCartaResponse:
        """Orquesta el flujo de envío de carta para evaluación.

        Args:
            imagen_frente: bytes del frente de la carta.
            content_type_frente: MIME type declarado por el cliente.
            imagen_reverso: bytes del reverso de la carta.
            content_type_reverso: MIME type declarado por el cliente.
            submitter_id: ID del usuario que envía.
            correlation_id: ID de correlación del request.

        Returns:
            EnviarCartaResponse con identificador y estado.

        Raises:
            ErrorValidacion: si alguna validación falla.
        """
        imagenes = self._validar_imagenes(
            imagen_frente, content_type_frente, imagen_reverso, content_type_reverso
        )
        calidad = self._calcular_calidad(imagen_frente, imagen_reverso)
        saturado, tiempo_estimado = await self._evaluar_saturacion()

        evaluacion_id = uuid.uuid4()
        subidas = await self._subir_imagenes(
            evaluacion_id, imagen_frente, imagenes.mime_frente,
            imagen_reverso, imagenes.mime_reverso,
        )

        evaluacion = await self._persistir_evaluacion(
            evaluacion_id, submitter_id, correlation_id, calidad, subidas
        )

        return self._construir_respuesta(evaluacion, calidad, saturado, tiempo_estimado)

    # ------------------------------------------------------------------
    # Paso 1: validar formato, tamaño y polyglot rejection
    # ------------------------------------------------------------------

    @staticmethod
    def _validar_imagenes(
        imagen_frente: bytes,
        content_type_frente: str,
        imagen_reverso: bytes,
        content_type_reverso: str,
    ) -> _ImagenesValidadas:
        """Valida ambas imágenes contra las reglas comunes del sistema.

        Raises:
            ErrorValidacion: si alguna imagen no cumple formato/tamaño.
        """
        mime_frente = reglas_imagen.validar_imagen(
            imagen_frente,
            content_type_cliente=content_type_frente,
            campo="imagen_frente",
        )
        mime_reverso = reglas_imagen.validar_imagen(
            imagen_reverso,
            content_type_cliente=content_type_reverso,
            campo="imagen_reverso",
        )
        return _ImagenesValidadas(mime_frente, mime_reverso)

    # ------------------------------------------------------------------
    # Paso 2: Image Quality Score
    # ------------------------------------------------------------------

    @staticmethod
    def _calcular_calidad(imagen_frente: bytes, imagen_reverso: bytes) -> _CalidadImagen:
        """Calcula el IQ Score de ambas imágenes y rechaza si no alcanzan
        el umbral mínimo.

        Raises:
            ErrorValidacion: si alguna imagen tiene calidad insuficiente.
        """
        iq_frente = calcular_iq_score(imagen_frente, campo="imagen_frente")
        iq_reverso = calcular_iq_score(imagen_reverso, campo="imagen_reverso")

        if iq_frente < UMBRAL_IQS_DEFAULT:
            raise ErrorValidacion(
                codigo="iq_score_insuficiente",
                mensaje=(
                    f"La calidad de la imagen del frente es insuficiente "
                    f"(score: {iq_frente:.2f}, mínimo: {UMBRAL_IQS_DEFAULT}). "
                    "Intentá recapturar con mejor iluminación y enfoque."
                ),
                campo="imagen_frente",
            )
        if iq_reverso < UMBRAL_IQS_DEFAULT:
            raise ErrorValidacion(
                codigo="iq_score_insuficiente",
                mensaje=(
                    f"La calidad de la imagen del reverso es insuficiente "
                    f"(score: {iq_reverso:.2f}, mínimo: {UMBRAL_IQS_DEFAULT}). "
                    "Intentá recapturar con mejor iluminación y enfoque."
                ),
                campo="imagen_reverso",
            )

        return _CalidadImagen(iq_frente, iq_reverso)

    # ------------------------------------------------------------------
    # Paso 3: verificar saturación de la cola
    # ------------------------------------------------------------------

    async def _evaluar_saturacion(self) -> tuple[bool, int | None]:
        """Determina si el sistema está saturado de evaluaciones pendientes.

        Returns:
            (saturado, tiempo_estimado_segundos) — el tiempo es None si
            no está saturado.
        """
        pendientes = await self._repo.contar_pendientes()
        saturado = pendientes >= UMBRAL_SATURACION
        tiempo_estimado = TIEMPO_ESTIMADO_SATURACION_SEGUNDOS if saturado else None
        return saturado, tiempo_estimado

    # ------------------------------------------------------------------
    # Paso 4: subir imágenes a Blob Storage (con limpieza compensatoria)
    # ------------------------------------------------------------------

    async def _subir_imagenes(
        self,
        evaluacion_id: uuid.UUID,
        imagen_frente: bytes,
        mime_frente: str,
        imagen_reverso: bytes,
        mime_reverso: str,
    ) -> _ImagenesSubidas:
        """Sube frente y reverso a Blob Storage.

        Si la subida del reverso falla después de que el frente ya se
        subió, el frente se elimina para no dejar un blob huérfano.
        """
        contenedor = CONTENEDOR_EVALUACIONES
        clave_frente = f"evaluaciones/{evaluacion_id}/frente.{EXTENSION_POR_MIME[mime_frente]}"
        clave_reverso = f"evaluaciones/{evaluacion_id}/reverso.{EXTENSION_POR_MIME[mime_reverso]}"

        try:
            url_frente = await self._almacenamiento.guardar(
                contenedor, clave_frente, imagen_frente, mime_frente
            )
        except Exception as exc:
            logger.error(
                "error_subiendo_imagen_frente",
                evaluacion_id=str(evaluacion_id),
                clave=clave_frente,
            )
            raise exc

        try:
            url_reverso = await self._almacenamiento.guardar(
                contenedor, clave_reverso, imagen_reverso, mime_reverso
            )
        except Exception:
            await eliminar_blob_silencioso(contenedor, clave_frente, logger)
            raise

        return _ImagenesSubidas(url_frente, clave_frente, url_reverso, clave_reverso)

    # ------------------------------------------------------------------
    # Paso 5: persistir en BD como unidad de trabajo atómica
    # ------------------------------------------------------------------

    async def _persistir_evaluacion(
        self,
        evaluacion_id: uuid.UUID,
        submitter_id: uuid.UUID,
        correlation_id: str | None,
        calidad: _CalidadImagen,
        subidas: _ImagenesSubidas,
    ) -> Evaluacion:
        """Crea y guarda el registro de evaluación.

        Si la escritura en BD falla, los blobs ya subidos a Azure quedan
        huérfanos y se limpian antes de propagar la excepción.
        """
        evaluacion = Evaluacion(
            id=evaluacion_id,
            identificador_evaluacion=_generar_identificador(evaluacion_id),
            submitter_id=submitter_id,
            estado="pendiente",
            url_imagen_frente=subidas.url_frente,
            clave_blob_frente=subidas.clave_frente,
            url_imagen_reverso=subidas.url_reverso,
            clave_blob_reverso=subidas.clave_reverso,
            correlation_id=correlation_id,
            iq_score_frente=calidad.iq_frente,
            iq_score_reverso=calidad.iq_reverso,
        )

        try:
            async with unidad_de_trabajo(self._sesion):
                await self._repo.guardar(evaluacion)
        except Exception:
            await eliminar_blob_silencioso(
                CONTENEDOR_EVALUACIONES, subidas.clave_frente, logger
            )
            if subidas.clave_reverso is not None:
                await eliminar_blob_silencioso(
                    CONTENEDOR_EVALUACIONES, subidas.clave_reverso, logger
                )
            raise

        logger.info(
            "evaluacion_pendiente",
            evaluacion_id=str(evaluacion_id),
            identificador=evaluacion.identificador_evaluacion,
            submitter_id=str(submitter_id),
            iq_frente=calidad.iq_frente,
            iq_reverso=calidad.iq_reverso,
        )

        return evaluacion

    # ------------------------------------------------------------------
    # Construcción de la respuesta final
    # ------------------------------------------------------------------

    @staticmethod
    def _construir_respuesta(
        evaluacion: Evaluacion,
        calidad: _CalidadImagen,
        saturado: bool,
        tiempo_estimado: int | None,
    ) -> EnviarCartaResponse:
        mensaje = (
            f"Evaluación registrada correctamente. "
            f"Tu identificador es {evaluacion.identificador_evaluacion}."
        )
        if saturado:
            mensaje += (
                f" El sistema está procesando muchas solicitudes. "
                f"Tiempo estimado: {tiempo_estimado} segundos."
            )

        return EnviarCartaResponse(
            identificador_evaluacion=evaluacion.identificador_evaluacion,
            estado="pendiente",
            iq_score_frente=calidad.iq_frente,
            iq_score_reverso=calidad.iq_reverso,
            mensaje=mensaje,
            tiempo_estimado_segundos=tiempo_estimado,
            created_at=evaluacion.created_at,
        )