"""Servicio de aplicación: preprocesar carta (US 191).

Segundo paso del pipeline de evaluación, encadenado automáticamente
después de `EnviarCartaService` (Sprint 3). Orquesta:

1. `_obtener_evaluacion_pendiente` — carga la evaluación a procesar
2. `_marcar_preprocesando`         — transición de estado (DA-01: el
                                      estado se persiste antes de
                                      procesar, nunca se pierde una
                                      evaluación si el proceso falla)
3. `_descargar_imagenes`           — trae los bytes originales del Blob
4. `_preprocesar_ambas_caras`      — corrección, recorte, normalización
                                      y segmentación (alterno: deriva a
                                      revisión manual o rechazo)
5. `_persistir_resultado`          — guarda imágenes procesadas +
                                      regiones, transición a CALIFICANDO

Si el preprocesamiento se completa exitosamente, el pipeline continúa
automáticamente hacia `CalificarCartaService` (US 193).
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.almacenamiento import IAlmacenamientoImagenes
from pokegrading.compartido.errores import ErrorNoEncontrado, ErrorSolicitudInvalida
from pokegrading.compartido.logging import obtener_logger
from pokegrading.datos.db import unidad_de_trabajo
from pokegrading.negocio.evaluaciones.algoritmo.vision_preprocesamiento import (
    ImagenPreprocesada,
    preprocesar_imagen,
)
from pokegrading.negocio.evaluaciones.modelos import Evaluacion
from pokegrading.negocio.evaluaciones.repositorio import EvaluacionRepositorio
from pokegrading.negocio.evaluaciones.tipos import CaraCarta, EstadoEvaluacion

logger = obtener_logger(__name__)

CONTENEDOR_EVALUACIONES = "cartas-referencia"
MIME_SALIDA_PREPROCESAMIENTO = "image/jpeg"


class PreprocesarCartaService:
    """Caso de uso: preprocesar las imágenes de una evaluación pendiente."""

    def __init__(
        self,
        sesion: AsyncSession,
        almacenamiento: IAlmacenamientoImagenes,
    ) -> None:
        self._sesion = sesion
        self._repo = EvaluacionRepositorio(sesion)
        self._almacenamiento = almacenamiento

    # ------------------------------------------------------------------
    # Orquestador
    # ------------------------------------------------------------------

    async def ejecutar(self, evaluacion_id: uuid.UUID) -> Evaluacion:
        """Ejecuta el preprocesamiento de una evaluación pendiente.

        Args:
            evaluacion_id: ID de la evaluación a preprocesar (creada
                por `EnviarCartaService`).

        Returns:
            La evaluación actualizada, en estado `calificando` si tuvo
            éxito, o `revision_manual`/`rechazada` según el alterno
            que haya aplicado.

        Raises:
            ErrorNoEncontrado: si la evaluación no existe.
        """
        evaluacion = await self._obtener_evaluacion_pendiente(evaluacion_id)
        await self._marcar_preprocesando(evaluacion)

        bytes_frente, bytes_reverso = await self._descargar_imagenes(evaluacion)

        try:
            resultado_frente, resultado_reverso = self._preprocesar_ambas_caras(
                bytes_frente, bytes_reverso
            )
        except ErrorSolicitudInvalida as exc:
            await self._derivar_segun_error(evaluacion, exc)
            return evaluacion

        await self._persistir_resultado(evaluacion, resultado_frente, resultado_reverso)

        return evaluacion

    # ------------------------------------------------------------------
    # Paso 1: cargar la evaluación
    # ------------------------------------------------------------------

    async def _obtener_evaluacion_pendiente(
        self, evaluacion_id: uuid.UUID
    ) -> Evaluacion:
        """Carga la evaluación a procesar.

        Raises:
            ErrorNoEncontrado: si no existe una evaluación con ese ID.
        """
        evaluacion = await self._repo.obtener_por_id(evaluacion_id)
        if evaluacion is None:
            raise ErrorNoEncontrado(
                codigo="evaluacion_no_encontrada",
                mensaje=f"No existe una evaluación con ID '{evaluacion_id}'.",
            )
        return evaluacion

    # ------------------------------------------------------------------
    # Paso 2: transición de estado ANTES de procesar (DA-01)
    # ------------------------------------------------------------------

    async def _marcar_preprocesando(self, evaluacion: Evaluacion) -> None:
        """Persiste la transición a `preprocesando` antes de iniciar el
        trabajo pesado, para que un fallo del proceso dependa de su
        propia idempotencia y no pierda el registro de "se estaba
        intentando" (DA-01: durabilidad del flujo multi-etapa).
        """
        evaluacion.estado = EstadoEvaluacion.PREPROCESANDO.value
        async with unidad_de_trabajo(self._sesion):
            pass  # el cambio en `evaluacion` ya está trackeado por la sesión

    # ------------------------------------------------------------------
    # Paso 3: descargar imágenes originales
    # ------------------------------------------------------------------

    async def _descargar_imagenes(self, evaluacion: Evaluacion) -> tuple[bytes, bytes]:
        """Descarga los bytes originales subidos en `EnviarCartaService`."""
        bytes_frente = await self._almacenamiento.descargar(
            CONTENEDOR_EVALUACIONES, evaluacion.clave_blob_frente
        )
        bytes_reverso = await self._almacenamiento.descargar(
            CONTENEDOR_EVALUACIONES, evaluacion.clave_blob_reverso
        )
        return bytes_frente, bytes_reverso

    # ------------------------------------------------------------------
    # Paso 4: preprocesar ambas caras
    # ------------------------------------------------------------------

    @staticmethod
    def _preprocesar_ambas_caras(
        bytes_frente: bytes, bytes_reverso: bytes
    ) -> tuple[ImagenPreprocesada, ImagenPreprocesada]:
        """Aplica corrección de perspectiva, recorte, normalización y
        segmentación a ambas caras.

        Raises:
            ErrorValidacion: `fondo_no_aislable` o `distorsion_no_corregible`,
                propagado tal cual desde `preprocesar_imagen` para que el
                llamador decida el alterno correspondiente.
        """
        resultado_frente = preprocesar_imagen(
            bytes_frente, campo=CaraCarta.FRENTE.value
        )
        resultado_reverso = preprocesar_imagen(
            bytes_reverso, campo=CaraCarta.REVERSO.value
        )
        return resultado_frente, resultado_reverso

    # ------------------------------------------------------------------
    # Alterno: derivar a revisión manual o rechazo según el tipo de error
    # ------------------------------------------------------------------

    async def _derivar_segun_error(
        self, evaluacion: Evaluacion, error: ErrorSolicitudInvalida
    ) -> None:
        """Aplica los alternos de la US:

        - `fondo_no_aislable` → revisión manual (la carta es legítima
          pero el sistema no puede procesarla automáticamente).
        - `distorsion_no_corregible` → rechazo (se solicita recapturar;
          no tiene sentido escalar a un humano una foto inutilizable).
        """
        if error.codigo == "fondo_no_aislable":
            evaluacion.estado = EstadoEvaluacion.REVISION_MANUAL.value
            evaluacion.motivo_revision_manual = error.mensaje
            evento = "evaluacion_derivada_revision_manual"
        else:
            evaluacion.estado = EstadoEvaluacion.RECHAZADA.value
            evaluacion.motivo_rechazo = error.mensaje
            evento = "evaluacion_rechazada_preprocesamiento"

        async with unidad_de_trabajo(self._sesion):
            pass

        logger.warning(
            evento,
            evaluacion_id=str(evaluacion.id),
            codigo_error=error.codigo,
        )

    # ------------------------------------------------------------------
    # Paso 5: persistir resultado y avanzar el pipeline
    # ------------------------------------------------------------------

    async def _persistir_resultado(
        self,
        evaluacion: Evaluacion,
        resultado_frente: ImagenPreprocesada,
        resultado_reverso: ImagenPreprocesada,
    ) -> None:
        """Sube las imágenes procesadas, guarda las regiones segmentadas
        y avanza el estado a `calificando`.
        """
        clave_frente = f"evaluaciones/{evaluacion.id}/frente_procesada.jpg"
        clave_reverso = f"evaluaciones/{evaluacion.id}/reverso_procesada.jpg"

        await self._almacenamiento.guardar(
            CONTENEDOR_EVALUACIONES,
            clave_frente,
            resultado_frente.bytes_normalizados,
            MIME_SALIDA_PREPROCESAMIENTO,
        )
        await self._almacenamiento.guardar(
            CONTENEDOR_EVALUACIONES,
            clave_reverso,
            resultado_reverso.bytes_normalizados,
            MIME_SALIDA_PREPROCESAMIENTO,
        )

        evaluacion.clave_blob_frente_procesada = clave_frente
        evaluacion.clave_blob_reverso_procesada = clave_reverso
        evaluacion.regiones_segmentadas = {
            CaraCarta.FRENTE.value: resultado_frente.regiones,
            CaraCarta.REVERSO.value: resultado_reverso.regiones,
        }
        evaluacion.estado = EstadoEvaluacion.CALIFICANDO.value

        async with unidad_de_trabajo(self._sesion):
            pass

        logger.info(
            "evaluacion_preprocesada",
            evaluacion_id=str(evaluacion.id),
        )