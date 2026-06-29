"""Servicio de aplicación: calificar carta (US 193).

Tercer y último paso del pipeline de evaluación, encadenado
automáticamente después de `PreprocesarCartaService` cuando éste
termina en estado `calificando`. Orquesta:

1. `_obtener_evaluacion_calificando` — carga la evaluación a calificar
2. `_recortar_regiones`              — recorta las 4 regiones por cara
                                         a partir de las coordenadas
                                         guardadas por el preprocesamiento
3. `_obtener_baselines`              — carga baseline específico
                                         (set, acabado) si existe, y
                                         el global como fallback
4. `_calcular_calificacion`          — aplica el algoritmo de scoring
                                         (alterno: deriva a revisión
                                         manual si una dimensión no
                                         puede calcularse o el
                                         resultado es incoherente)
5. `_persistir_calificacion`         — guarda subgrades, grado final,
                                         versión de algoritmo (DA-08) y
                                         marca la evaluación completada

Idempotencia (US 193): antes de procesar, se verifica si ya existe una
evaluación con la misma `clave_idempotencia` (derivada de submitter +
hashes de imagen). Si existe, se retorna esa evaluación sin reprocesar.
"""

from __future__ import annotations

import hashlib
import uuid
from io import BytesIO

import numpy as np
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.almacenamiento import IAlmacenamientoImagenes
from pokegrading.compartido.errores import ErrorNoEncontrado
from pokegrading.compartido.logging import obtener_logger
from pokegrading.datos.db import unidad_de_trabajo
from pokegrading.negocio.evaluaciones.algoritmo.scoring_subgrades import (
    ReferenciaBaseline,
    ResultadoCalificacion,
    calcular_calificacion,
)
from pokegrading.negocio.evaluaciones.modelos import Evaluacion, GradingBaseline
from pokegrading.negocio.evaluaciones.repositorio import (
    EvaluacionRepositorio,
    GradingBaselineRepositorio,
)
from pokegrading.negocio.evaluaciones.tipos import (
    CaraCarta,
    EstadoEvaluacion,
    RegionCarta,
)

logger = obtener_logger(__name__)

CONTENEDOR_EVALUACIONES = "cartas-referencia"


def _a_referencia_baseline(
    baseline: GradingBaseline, *, es_global: bool
) -> ReferenciaBaseline:
    """Convierte el modelo ORM a la vista desacoplada que usa el algoritmo puro."""
    return ReferenciaBaseline(
        id=str(baseline.id),
        referencia_centering=baseline.referencia_centering,
        referencia_corners=baseline.referencia_corners,
        referencia_edges=baseline.referencia_edges,
        referencia_surface=baseline.referencia_surface,
        tamano_muestra=baseline.tamano_muestra,
        version_algoritmo=baseline.version_algoritmo,
        es_global=es_global,
    )


class CalificarCartaService:
    """Caso de uso: calcular subgrades y grado estimado de una evaluación."""

    def __init__(
        self,
        sesion: AsyncSession,
        almacenamiento: IAlmacenamientoImagenes,
    ) -> None:
        self._sesion = sesion
        self._repo = EvaluacionRepositorio(sesion)
        self._repo_baseline = GradingBaselineRepositorio(sesion)
        self._almacenamiento = almacenamiento

    # ------------------------------------------------------------------
    # Orquestador
    # ------------------------------------------------------------------

    async def ejecutar(
        self, evaluacion_id: uuid.UUID, *, set_codigo: str, acabado: str
    ) -> Evaluacion:
        """Ejecuta la calificación de una evaluación en estado `calificando`.

        Args:
            evaluacion_id: ID de la evaluación a calificar.
            set_codigo: set de la carta (para seleccionar baseline).
            acabado: acabado de la carta (para seleccionar baseline).

        Returns:
            La evaluación actualizada, en estado `completada` si pudo
            calificarse, o `revision_manual` si algún subgrade no fue
            calculable o el resultado no pasó la regla de coherencia.

        Raises:
            ErrorNoEncontrado: si la evaluación no existe.
        """
        evaluacion = await self._obtener_evaluacion_calificando(evaluacion_id)

        evaluacion_existente = await self._verificar_idempotencia(evaluacion)
        if evaluacion_existente is not None:
            return evaluacion_existente

        regiones = await self._recortar_regiones(evaluacion)
        baseline_especifico, baseline_global = await self._obtener_baselines(
            set_codigo, acabado
        )

        resultado = self._calcular_calificacion(
            regiones, baseline_especifico, baseline_global
        )

        await self._persistir_calificacion(evaluacion, resultado, baseline_global)

        return evaluacion

    # ------------------------------------------------------------------
    # Paso 1: cargar la evaluación
    # ------------------------------------------------------------------

    async def _obtener_evaluacion_calificando(
        self, evaluacion_id: uuid.UUID
    ) -> Evaluacion:
        """Carga la evaluación a calificar.

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
    # Idempotencia (US 193: "la operación es idempotente")
    # ------------------------------------------------------------------

    @staticmethod
    def _calcular_clave_idempotencia(evaluacion: Evaluacion) -> str:
        """Deriva una clave determinística de (submitter, imágenes originales).

        Dos envíos de la misma carta por el mismo submitter producen
        la misma clave, sin necesidad de que el cliente envíe un
        identificador explícito.
        """
        base = f"{evaluacion.submitter_id}:{evaluacion.clave_blob_frente}:{evaluacion.clave_blob_reverso}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    async def _verificar_idempotencia(
        self, evaluacion: Evaluacion
    ) -> Evaluacion | None:
        """Si ya existe una evaluación completada con la misma clave de
        idempotencia, la devuelve sin reprocesar.

        Returns:
            La evaluación previa si es un reintento, o None si se debe
            continuar con el procesamiento normal.
        """
        clave = self._calcular_clave_idempotencia(evaluacion)
        evaluacion.clave_idempotencia = clave

        previa = await self._repo.obtener_por_clave_idempotencia(clave)
        if (
            previa is not None
            and previa.id != evaluacion.id
            and previa.grado_estimado is not None
        ):
            logger.info(
                "calificacion_reintento_idempotente",
                evaluacion_id=str(evaluacion.id),
                evaluacion_original_id=str(previa.id),
            )
            return previa

        return None

    # ------------------------------------------------------------------
    # Paso 2: recortar las 4 regiones de cada cara
    # ------------------------------------------------------------------

    async def _recortar_regiones(self, evaluacion: Evaluacion) -> dict[str, np.ndarray]:
        """Descarga las imágenes ya preprocesadas y recorta cada región
        segmentada a un array de píxeles, listo para el algoritmo de scoring.

        Combina frente y reverso por dimensión: cada subgrade se calcula
        sobre el promedio de información de ambas caras donde aplique
        (en este sprint, se usa la cara frente como referencia principal
        por ser la única con segmentación completa garantizada).
        """
        bytes_frente = await self._almacenamiento.descargar(
            CONTENEDOR_EVALUACIONES, evaluacion.clave_blob_frente_procesada
        )
        img_frente = np.array(Image.open(BytesIO(bytes_frente)).convert("L"))

        regiones_coords = (evaluacion.regiones_segmentadas or {}).get(
            CaraCarta.FRENTE.value, {}
        )

        regiones: dict[str, np.ndarray] = {}
        for dimension in RegionCarta:
            coords = regiones_coords.get(dimension.value)
            if coords is None:
                continue
            x0, y0, x1, y1 = coords
            regiones[dimension.value] = img_frente[y0:y1, x0:x1]

        return regiones

    # ------------------------------------------------------------------
    # Paso 3: baselines (específico + global, con fallback)
    # ------------------------------------------------------------------

    async def _obtener_baselines(
        self, set_codigo: str, acabado: str
    ) -> tuple[ReferenciaBaseline | None, ReferenciaBaseline]:
        """Carga el baseline específico de (set, acabado) si existe, y
        el baseline global (siempre presente, usado como fallback).
        """
        especifico_orm = await self._repo_baseline.obtener_especifico(
            set_codigo, acabado
        )
        global_orm = await self._repo_baseline.obtener_global()

        especifico = (
            _a_referencia_baseline(especifico_orm, es_global=False)
            if especifico_orm is not None
            else None
        )
        global_ref = _a_referencia_baseline(global_orm, es_global=True)

        return especifico, global_ref

    # ------------------------------------------------------------------
    # Paso 4: calcular subgrades, grado final y banda de incertidumbre
    # ------------------------------------------------------------------

    @staticmethod
    def _calcular_calificacion(
        regiones: dict[str, np.ndarray],
        baseline_especifico: ReferenciaBaseline | None,
        baseline_global: ReferenciaBaseline,
    ) -> ResultadoCalificacion:
        """Delega al algoritmo puro de scoring (negocio/evaluaciones/algoritmo.scoring_subgrades.py)."""
        return calcular_calificacion(regiones, baseline_especifico, baseline_global)

    # ------------------------------------------------------------------
    # Paso 5: persistir resultado (alterno: revisión manual si aplica)
    # ------------------------------------------------------------------

    async def _persistir_calificacion(
        self,
        evaluacion: Evaluacion,
        resultado: ResultadoCalificacion,
        baseline_global: ReferenciaBaseline,
    ) -> None:
        """Guarda los subgrades calculados y avanza el estado final.

        Alterno de la US: "Si algún subgrade no puede calcularse con
        insumos suficientes, la carta se deriva a calificación manual."
        y "Si el resultado contradice umbrales mínimos de coherencia
        interna, se deriva a revisión humana."
        """
        evaluacion.subgrade_centering = resultado.subgrade_centering
        evaluacion.subgrade_corners = resultado.subgrade_corners
        evaluacion.subgrade_edges = resultado.subgrade_edges
        evaluacion.subgrade_surface = resultado.subgrade_surface
        evaluacion.grado_estimado = resultado.grado_estimado
        evaluacion.banda_incertidumbre = resultado.banda_incertidumbre
        evaluacion.version_algoritmo_grading = baseline_global.version_algoritmo

        if (
            resultado.dimension_no_calculable is not None
            or resultado.grado_estimado is None
        ):
            evaluacion.estado = EstadoEvaluacion.REVISION_MANUAL.value
            evaluacion.motivo_revision_manual = (
                f"No fue posible calcular el subgrade de "
                f"'{resultado.dimension_no_calculable}' con insumos suficientes."
            )
            evento = "evaluacion_derivada_revision_manual_calificacion"
        else:
            evaluacion.estado = EstadoEvaluacion.COMPLETADA.value
            evento = "evaluacion_completada"

        async with unidad_de_trabajo(self._sesion):
            pass  # los cambios en `evaluacion` ya están trackeados por la sesión

        logger.info(
            evento,
            evaluacion_id=str(evaluacion.id),
            grado_estimado=resultado.grado_estimado,
            version_algoritmo=baseline_global.version_algoritmo,
        )
