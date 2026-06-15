"""Modelo ORM `Usuario`.

Tabla: `usuarios` (snake_case, V6 §3.1).
Columnas: snake_case.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pokegrading.datos.db import Base
from pokegrading.negocio.usuarios.tipos import Idioma, Pais, Rol


class Usuario(Base):
    """Cuenta de usuario de PokéGrading.

    Cubre los criterios de aceptación de la US "Registrar cuenta":
    - ID autogenerado (UUID v4)
    - correo único
    - rol Submitter por default
    - timestamps UTC de creación y último login
    - aceptación versionada de disclosure
    """

    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    correo: Mapped[str] = mapped_column(
        String(254),  # RFC 5321 práctico máximo
        unique=True,
        index=True,
        nullable=False,
    )
    alias: Mapped[str] = mapped_column(String(50), nullable=False)
    hash_password: Mapped[str] = mapped_column(String(255), nullable=False)

    pais: Mapped[Pais] = mapped_column(
        Enum(Pais, name="pais_enum", values_callable=lambda e: [v.value for v in e]),
        nullable=False,
    )
    idioma_preferido: Mapped[Idioma] = mapped_column(
        Enum(
            Idioma, name="idioma_enum", values_callable=lambda e: [v.value for v in e]
        ),
        nullable=False,
        default=Idioma.ES,
    )
    rol: Mapped[Rol] = mapped_column(
        Enum(Rol, name="rol_enum", values_callable=lambda e: [v.value for v in e]),
        nullable=False,
        default=Rol.SUBMITTER,
    )

    # Disclosure (CR-03, U9): se persiste la versión exacta del texto aceptado
    disclosure_aceptado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    disclosure_version: Mapped[str] = mapped_column(String(20), nullable=False)
    disclosure_aceptado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Timestamps UTC
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Usuario id={self.id} correo={self.correo} rol={self.rol}>"
