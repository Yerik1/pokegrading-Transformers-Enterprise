"""Modelo ORM Evaluacion (tabla evaluaciones).

Registra cada solicitud de evaluación de carta enviada por un Submitter.
Inmutable tras su creación (DA-03): los resultados se agregan como
campos opcionales, nunca se modifica el registro original.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pokegrading.compartido.db import Base


class Evaluacion(Base):
    """Solicitud de evaluación de una carta."""

    __tablename__ = "evaluaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    identificador_evaluacion: Mapped[str] = mapped_column(
        String(30), nullable=False, unique=True
    )
    submitter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pendiente"
    )
    url_imagen_frente: Mapped[str] = mapped_column(Text, nullable=False)
    clave_blob_frente: Mapped[str] = mapped_column(Text, nullable=False)
    url_imagen_reverso: Mapped[str] = mapped_column(Text, nullable=False)
    clave_blob_reverso: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    iq_score_frente: Mapped[float | None] = mapped_column(Float, nullable=True)
    iq_score_reverso: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Evaluacion id={self.id} {self.identificador_evaluacion}>"
