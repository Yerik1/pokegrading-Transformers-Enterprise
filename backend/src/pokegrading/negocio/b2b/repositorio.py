"""Repositorio módulo B2B.
 
Aísla SQLAlchemy del servicio. El servicio trabaja con métodos semánticos
y nunca escribe SQL directamente.
"""
 
from __future__ import annotations
 
import uuid
from datetime import UTC, datetime, timedelta
 
from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
 
from pokegrading.negocio.b2b.modelos import B2BCuenta, B2BConsultaAuditoria, B2BRateLimit
 
 
class B2BRepositorio:
    """Acceso a datos de las tres tablas B2B."""
 
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion
 
    # ------------------------------------------------------------------
    # Autenticación por API key
    # ------------------------------------------------------------------
 
    async def obtener_cuenta_por_hash(self, api_key_hash: str) -> B2BCuenta | None:
        """Busca una cuenta por el hash SHA-256 de su API key."""
        stmt = select(B2BCuenta).where(B2BCuenta.api_key_hash == api_key_hash)
        resultado = await self._sesion.execute(stmt)
        return resultado.scalar_one_or_none()
 
    # ------------------------------------------------------------------
    # Idempotencia
    # ------------------------------------------------------------------
 
    async def obtener_consulta_por_idempotency_key(
        self,
        cuenta_id: uuid.UUID,
        idempotency_key: str,
        ventana_segundos: int,
    ) -> B2BConsultaAuditoria | None:
        """Busca un registro de auditoría previo dentro de la ventana de idempotencia.
 
        Solo considera registros creados dentro de los últimos `ventana_segundos`.
        """
        desde = datetime.now(UTC) - timedelta(seconds=ventana_segundos)
        stmt = select(B2BConsultaAuditoria).where(
            and_(
                B2BConsultaAuditoria.cuenta_id == cuenta_id,
                B2BConsultaAuditoria.idempotency_key == idempotency_key,
                B2BConsultaAuditoria.created_at >= desde,
            )
        )
        resultado = await self._sesion.execute(stmt)
        return resultado.scalar_one_or_none()
 
    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
 
    async def obtener_cartas_consultadas_mes(
        self, cuenta_id: uuid.UUID, anio: int, mes: int
    ) -> int:
        """Devuelve el total de cartas consultadas en el mes dado. 0 si no existe registro."""
        stmt = select(B2BRateLimit.cartas_consultadas).where(
            and_(
                B2BRateLimit.cuenta_id == cuenta_id,
                B2BRateLimit.anio == anio,
                B2BRateLimit.mes == mes,
            )
        )
        resultado = await self._sesion.execute(stmt)
        valor = resultado.scalar_one_or_none()
        return valor if valor is not None else 0
 
    async def incrementar_cartas_consultadas(
        self,
        cuenta_id: uuid.UUID,
        anio: int,
        mes: int,
        cantidad: int,
    ) -> None:
        """Incrementa el contador de cartas del mes. Crea el registro si no existe (upsert).
 
        Usa INSERT ... ON CONFLICT DO UPDATE para ser atómico y evitar race conditions.
        """
        nuevo_id = uuid.uuid4()
        stmt = pg_insert(B2BRateLimit).values(
            id=nuevo_id,
            cuenta_id=cuenta_id,
            anio=anio,
            mes=mes,
            cartas_consultadas=cantidad,
        ).on_conflict_do_update(
            constraint="uq_b2b_rate_limit_mes",
            set_={
                "cartas_consultadas": B2BRateLimit.cartas_consultadas + cantidad,
                "updated_at": datetime.now(UTC),
            },
        )
        await self._sesion.execute(stmt)
 
    # ------------------------------------------------------------------
    # Auditoría
    # ------------------------------------------------------------------
 
    async def registrar_consulta(
        self,
        *,
        cuenta_id: uuid.UUID,
        idempotency_key: str | None,
        total_cartas: int,
        correlation_id: str | None,
        respuesta_json: str,
        es_reintento: bool = False,
    ) -> B2BConsultaAuditoria:
        """Inserta un registro de auditoría. Append-only, nunca se modifica."""
        registro = B2BConsultaAuditoria(
            cuenta_id=cuenta_id,
            idempotency_key=idempotency_key,
            total_cartas=total_cartas,
            correlation_id=correlation_id,
            respuesta_json=respuesta_json,
            es_reintento=es_reintento,
        )
        self._sesion.add(registro)
        await self._sesion.flush()
        return registro