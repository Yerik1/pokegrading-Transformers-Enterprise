"""Repositorio de evaluaciones."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.negocio.evaluaciones.modelos import Evaluacion, GradingBaseline


class EvaluacionRepositorio:
    """Acceso a datos para evaluaciones."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def guardar(self, evaluacion: Evaluacion) -> None:
        """Persiste una evaluación nueva."""
        self._sesion.add(evaluacion)

    async def contar_pendientes(self) -> int:
        """Cuenta evaluaciones en estado pendiente, preprocesando o calificando."""
        stmt = select(func.count()).where(
            Evaluacion.estado.in_(["pendiente", "preprocesando", "calificando"])
        )
        resultado = await self._sesion.execute(stmt)
        return resultado.scalar_one()

    async def obtener_por_id(self, evaluacion_id: uuid.UUID) -> Evaluacion | None:
        """Busca una evaluación por su ID. None si no existe."""
        return await self._sesion.get(Evaluacion, evaluacion_id)

    async def obtener_por_identificador(
        self, identificador_evaluacion: str
    ) -> Evaluacion | None:
        """Busca una evaluación por su identificador legible (ej. EV-2026-...).

        Usado por `PipelineEvaluacionService` para resolver el UUID
        interno a partir de la respuesta pública de `EnviarCartaService`,
        sin que ese servicio necesite exponer el UUID en su contrato.
        """
        stmt = select(Evaluacion).where(
            Evaluacion.identificador_evaluacion == identificador_evaluacion
        )
        resultado = await self._sesion.execute(stmt)
        return resultado.scalar_one_or_none()

    async def obtener_por_clave_idempotencia(
        self, clave_idempotencia: str
    ) -> Evaluacion | None:
        """Busca una evaluación previa con la misma clave de idempotencia
        (US 193: "reintentar el envío con la misma carta y sesión no
        genera evaluaciones duplicadas").
        """
        stmt = select(Evaluacion).where(
            Evaluacion.clave_idempotencia == clave_idempotencia
        )
        resultado = await self._sesion.execute(stmt)
        return resultado.scalar_one_or_none()


class GradingBaselineRepositorio:
    """Acceso a datos para los baselines de calificación (US 193)."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_especifico(
        self, set_codigo: str, acabado: str
    ) -> GradingBaseline | None:
        """Busca el baseline calibrado para un (set_codigo, acabado) exacto."""
        stmt = select(GradingBaseline).where(
            GradingBaseline.set_codigo == set_codigo,
            GradingBaseline.acabado == acabado,
        )
        resultado = await self._sesion.execute(stmt)
        return resultado.scalar_one_or_none()

    async def obtener_global(self) -> GradingBaseline:
        """Obtiene el baseline global (fallback universal, set_codigo=None).

        Se asume que el baseline global siempre existe: se crea por
        seed/migración de datos antes de habilitar el pipeline de
        calificación en un ambiente nuevo. Si no existe, es un error
        de configuración del ambiente, no un caso de negocio a manejar
        con un Optional.
        """
        stmt = select(GradingBaseline).where(GradingBaseline.set_codigo.is_(None))
        resultado = await self._sesion.execute(stmt)
        return resultado.scalar_one()
