"""Servicio de aplicación: enviar carta para evaluación."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido import imagenes as reglas_imagen
from pokegrading.compartido.almacenamiento import IAlmacenamientoImagenes
from pokegrading.compartido.almacenamiento.base import EXTENSION_POR_MIME
from pokegrading.compartido.errores import ErrorValidacion
from pokegrading.compartido.logging import obtener_logger
from pokegrading.compartido.almacenamiento.base import eliminar_blob_silencioso
from pokegrading.negocio.evaluaciones.modelos import Evaluacion
from pokegrading.negocio.evaluaciones.reglas import UMBRAL_IQS_DEFAULT, calcular_iq_score
from pokegrading.negocio.evaluaciones.repositorio import EvaluacionRepositorio
from pokegrading.compartido.schemas.evaluaciones import EnviarCartaResponse

logger = obtener_logger(__name__)

UMBRAL_SATURACION = 50
TIEMPO_ESTIMADO_SATURACION_SEGUNDOS = 120
CONTENEDOR_EVALUACIONES = "cartas-referencia"


def _generar_identificador(evaluacion_id: uuid.UUID) -> str:
    """Genera identificador legible tipo EV-2026-05-31-A1B3."""
    hoy = datetime.now(UTC).strftime("%Y-%m-%d")
    sufijo = str(evaluacion_id).upper().replace("-", "")[:4]
    return f"EV-{hoy}-{sufijo}"


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
        # === 1. Validar formato, tamaño y polyglot ===
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

        # === 2. Image Quality Score ===
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

        # === 3. Verificar saturación ===
        pendientes = await self._repo.contar_pendientes()
        saturado = pendientes >= UMBRAL_SATURACION
        tiempo_estimado = TIEMPO_ESTIMADO_SATURACION_SEGUNDOS if saturado else None

        # === 4. Generar IDs y subir imágenes ===
        evaluacion_id = uuid.uuid4()
        identificador = _generar_identificador(evaluacion_id)
        contenedor = CONTENEDOR_EVALUACIONES

        clave_frente = (
            f"evaluaciones/{evaluacion_id}/frente" f".{EXTENSION_POR_MIME[mime_frente]}"
        )
        clave_reverso = (
            f"evaluaciones/{evaluacion_id}/reverso"
            f".{EXTENSION_POR_MIME[mime_reverso]}"
        )

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

        # === 5. Persistir evaluación ===
        evaluacion = Evaluacion(
            id=evaluacion_id,
            identificador_evaluacion=identificador,
            submitter_id=submitter_id,
            estado="pendiente",
            url_imagen_frente=url_frente,
            clave_blob_frente=clave_frente,
            url_imagen_reverso=url_reverso,
            clave_blob_reverso=clave_reverso,
            correlation_id=correlation_id,
            iq_score_frente=iq_frente,
            iq_score_reverso=iq_reverso,
        )

        await self._repo.guardar(evaluacion)
        await self._sesion.commit()

        logger.info(
            "evaluacion_pendiente",
            evaluacion_id=str(evaluacion_id),
            identificador=identificador,
            submitter_id=str(submitter_id),
            iq_frente=iq_frente,
            iq_reverso=iq_reverso,
            saturado=saturado,
        )

        mensaje = (
            f"Evaluación registrada correctamente. "
            f"Tu identificador es {identificador}."
        )
        if saturado:
            mensaje += (
                f" El sistema está procesando muchas solicitudes. "
                f"Tiempo estimado: {tiempo_estimado} segundos."
            )

        return EnviarCartaResponse(
            identificador_evaluacion=identificador,
            estado="pendiente",
            iq_score_frente=iq_frente,
            iq_score_reverso=iq_reverso,
            mensaje=mensaje,
            tiempo_estimado_segundos=tiempo_estimado,
            created_at=evaluacion.created_at,
        )

