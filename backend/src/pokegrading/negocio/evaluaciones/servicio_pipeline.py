"""Orquestador del pipeline de evaluación: enviar → preprocesar → calificar.

US 191 especifica que el preprocesamiento ocurre automáticamente al
recibir la carta, y US 193 que la calificación es el último paso del
mismo flujo. Este orquestador encadena los tres servicios ya existentes
(`EnviarCartaService`, `PreprocesarCartaService`, `CalificarCartaService`)
sin que ninguno de ellos conozca a los otros.

El response final incluye el estado real del pipeline y, si la evaluación
quedó completada, el grado estimado y los subgrades (US 193: "Yo como
Submitter quiero recibir un grado estimado de mi carta").
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.almacenamiento import IAlmacenamientoImagenes
from pokegrading.compartido.logging import obtener_logger
from pokegrading.compartido.schemas.evaluaciones import EnviarCartaResponse
from pokegrading.negocio.evaluaciones.modelos import Evaluacion
from pokegrading.negocio.evaluaciones.servicio import EnviarCartaService
from pokegrading.negocio.evaluaciones.servicio_calificar import CalificarCartaService
from pokegrading.negocio.evaluaciones.servicio_preprocesar import (
    PreprocesarCartaService,
)
from pokegrading.negocio.evaluaciones.tipos import EstadoEvaluacion

logger = obtener_logger(__name__)

# Estados en los que el pipeline se detiene y NO continúa al siguiente paso.
ESTADOS_TERMINALES_DE_PIPELINE: frozenset[str] = frozenset(
    {
        EstadoEvaluacion.REVISION_MANUAL.value,
        EstadoEvaluacion.RECHAZADA.value,
    }
)


class PipelineEvaluacionService:
    """Orquesta el flujo completo: enviar, preprocesar y calificar una carta."""

    def __init__(
        self,
        sesion: AsyncSession,
        almacenamiento: IAlmacenamientoImagenes,
    ) -> None:
        self._enviar = EnviarCartaService(sesion, almacenamiento)
        self._preprocesar = PreprocesarCartaService(sesion, almacenamiento)
        self._calificar = CalificarCartaService(sesion, almacenamiento)

    async def ejecutar(
        self,
        imagen_frente: bytes,
        content_type_frente: str,
        imagen_reverso: bytes,
        content_type_reverso: str,
        submitter_id: uuid.UUID,
        *,
        set_codigo: str,
        acabado: str,
        correlation_id: str | None = None,
    ) -> EnviarCartaResponse:
        """Ejecuta el pipeline completo y retorna el resultado al Submitter.

        El response incluye el estado final del pipeline y, si la evaluación
        quedó completada, el grado estimado, subgrades y banda de
        incertidumbre (US 193).
        """
        respuesta_inicial = await self._enviar.ejecutar(
            imagen_frente,
            content_type_frente,
            imagen_reverso,
            content_type_reverso,
            submitter_id,
            correlation_id,
        )

        evaluacion_id = self._enviar.ultima_evaluacion_id

        evaluacion = await self._continuar_pipeline(evaluacion_id, set_codigo, acabado)

        logger.info(
            "pipeline_evaluacion_finalizado",
            evaluacion_id=str(evaluacion.id),
            estado_final=evaluacion.estado,
        )

        # Enriquecer el response con el estado final y los resultados del
        # pipeline (US 193: el Submitter recibe el grado estimado en la
        # misma respuesta, sin necesidad de consultar un endpoint separado).
        return self._construir_respuesta_final(respuesta_inicial, evaluacion)

    async def _continuar_pipeline(
        self, evaluacion_id: uuid.UUID, set_codigo: str, acabado: str
    ) -> Evaluacion:
        """Ejecuta preprocesamiento y, si corresponde, calificación."""
        evaluacion = await self._preprocesar.ejecutar(evaluacion_id)

        if evaluacion.estado in ESTADOS_TERMINALES_DE_PIPELINE:
            return evaluacion

        return await self._calificar.ejecutar(
            evaluacion_id, set_codigo=set_codigo, acabado=acabado
        )

    @staticmethod
    def _construir_respuesta_final(
        respuesta_inicial: EnviarCartaResponse,
        evaluacion: Evaluacion,
    ) -> EnviarCartaResponse:
        """Combina la respuesta del envío con los resultados del pipeline.

        Reemplaza el estado 'pendiente' inicial por el estado real del
        pipeline, y agrega grado, subgrades y banda de incertidumbre si
        la evaluación quedó completada.
        """
        return EnviarCartaResponse(
            # Datos del envío original
            identificador_evaluacion=respuesta_inicial.identificador_evaluacion,
            iq_score_frente=respuesta_inicial.iq_score_frente,
            iq_score_reverso=respuesta_inicial.iq_score_reverso,
            mensaje=respuesta_inicial.mensaje,
            tiempo_estimado_segundos=respuesta_inicial.tiempo_estimado_segundos,
            created_at=respuesta_inicial.created_at,
            # Estado real del pipeline (reemplaza 'pendiente')
            estado=evaluacion.estado,
            # Resultados de calificación (None si no completó)
            grado_estimado=evaluacion.grado_estimado,
            banda_incertidumbre=evaluacion.banda_incertidumbre,
            subgrade_centering=evaluacion.subgrade_centering,
            subgrade_corners=evaluacion.subgrade_corners,
            subgrade_edges=evaluacion.subgrade_edges,
            subgrade_surface=evaluacion.subgrade_surface,
            version_algoritmo_grading=evaluacion.version_algoritmo_grading,
        )
