"""
Tablas:
- `b2b_cuentas`: tiendas registradas con su API key hasheada.
- `b2b_consultas_auditoria`: registro inmutable de cada lookup (DA-03, DA-06).
- `b2b_rate_limit`: contadores mensuales por cuenta para rate limiting.
 
Decisiones de diseño:
- La API key NUNCA se almacena en claro: solo su hash SHA-256 (DA-12,
  diseño de datos sensibles). El prefijo (primeros 8 chars) se guarda
  para mostrar en dashboards sin exponer la clave completa.
- Las consultas de auditoría son append-only (DA-03, idempotencia):
  el campo `idempotency_key` garantiza que reintentos no dupliquen registros.
- El rate limit se calcula sobre cartas consultadas, no sobre llamadas (US B2B).
"""
 
from __future__ import annotations
 
import uuid
from datetime import datetime
 
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
 
from pokegrading.compartido.db import Base
 
 
class B2BCuenta(Base):
    """Cuenta de servicio B2B (tienda / partner).
 
    Una cuenta representa a una tienda que accede vía API key.
    Relacionada con un Usuario de rol B2B_SERVICE_ACCOUNT.
    """
 
    __tablename__ = "b2b_cuentas"
 
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
 
    # Nombre de la tienda para dashboards y soporte
    nombre_tienda: Mapped[str] = mapped_column(String(200), nullable=False)
 
    # Hash SHA-256 de la API key (NUNCA la clave en claro — DA-12)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
 
    # Prefijo público (primeros 8 chars) para identificación en dashboards
    api_key_prefijo: Mapped[str] = mapped_column(String(8), nullable=False)
 
    # Estado de la cuenta
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    suspendida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    motivo_suspension: Mapped[str | None] = mapped_column(Text, nullable=True)
 
    # Límite de cartas consultadas por mes (configurable por cuenta)
    limite_cartas_mes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10_000
    )
 
    # Ventana de idempotencia en segundos (default: 5 minutos)
    ventana_idempotencia_segundos: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300
    )
 
    # Usuario de sistema asociado (rol B2B_SERVICE_ACCOUNT)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id"),
        nullable=False,
    )
 
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
 
    def __repr__(self) -> str:  # pragma: no cover
        return f"<B2BCuenta id={self.id} tienda={self.nombre_tienda} activa={self.activa}>"
 
 
class B2BConsultaAuditoria(Base):
    """Registro de auditoría de cada consulta B2B (append-only, DA-03).
 
    Nunca se modifica ni se borra. Si una consulta es reintento
    (mismo idempotency_key), se retorna la original sin insertar una nueva.
    """
 
    __tablename__ = "b2b_consultas_auditoria"
    __table_args__ = (
        # Unicidad de idempotency_key por cuenta (no global)
        UniqueConstraint("cuenta_id", "idempotency_key", name="uq_b2b_idempotencia"),
    )
 
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
 
    cuenta_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("b2b_cuentas.id"),
        nullable=False,
        index=True,
    )
 
    # Identificador de solicitud enviado por la tienda (opcional)
    # Usado para idempotencia dentro de la ventana configurada
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
 
    # Número de cartas en la consulta (para rate limiting — US: límite por cartas)
    total_cartas: Mapped[int] = mapped_column(Integer, nullable=False)
 
    # Correlation ID del request (DA-06)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
 
    # Respuesta serializada (para replay en reintentos idempotentes)
    respuesta_json: Mapped[str] = mapped_column(Text, nullable=False)
 
    # Flag: indica si fue servida desde caché de idempotencia
    es_reintento: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
 
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
 
    def __repr__(self) -> str:  # pragma: no cover
        return f"<B2BConsultaAuditoria id={self.id} cuenta={self.cuenta_id}>"
 
 
class B2BRateLimit(Base):
    """Contador de cartas consultadas por cuenta por mes.
 
    Se incrementa con cada consulta (excluye reintentos idempotentes).
    Se resetea al inicio de cada mes calendario.
    """
 
    __tablename__ = "b2b_rate_limit"
    __table_args__ = (
        UniqueConstraint("cuenta_id", "anio", "mes", name="uq_b2b_rate_limit_mes"),
    )
 
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
 
    cuenta_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("b2b_cuentas.id"),
        nullable=False,
        index=True,
    )
 
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
 
    # Total de cartas consultadas en el mes (no llamadas)
    cartas_consultadas: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
 
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
 
    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<B2BRateLimit cuenta={self.cuenta_id} "
            f"{self.anio}-{self.mes:02d} cartas={self.cartas_consultadas}>"
        )
 