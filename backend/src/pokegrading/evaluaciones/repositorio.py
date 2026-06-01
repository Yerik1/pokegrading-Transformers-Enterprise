"""Repositorio de evaluaciones."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.evaluaciones.modelos import Evaluacion


class EvaluacionRepositorio:
    """Acceso a datos para evaluaciones."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def guardar(self, evaluacion: Evaluacion) -> None:
        """Persiste una evaluación nueva."""
        self._sesion.add(evaluacion)

    async def contar_pendientes(self) -> int:
        """Cuenta evaluaciones en estado recibida o procesando."""
        from sqlalchemy import func, select

        stmt = select(func.count()).where(
            Evaluacion.estado.in_(["recibida", "procesando"])
        )
        resultado = await self._sesion.execute(stmt)
        return resultado.scalar_one()
