"""Modelo ORM `Carta` (tabla `cartas_catalogo`).

Cubre la US "Agregar carta al catálogo":
- `id` autogenerado e inmutable (DA-11: `card_id` interno)
- Identity tuple unique como índice compuesto (cero duplicados)
- Auditoría: autor + timestamps
- Referencias a Blob Storage (R8)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pokegrading.catalogo.tipos import (
    Acabado,
    Edicion,
    IdiomaCarta,
    Rareza,
    TipoPokemon,
)
from pokegrading.compartido.db import Base


class Carta(Base):
    """Entrada del catálogo de referencia de cartas."""

    __tablename__ = "cartas_catalogo"
    __table_args__ = (
        UniqueConstraint(
            "set_codigo",
            "numero",
            "edicion",
            "idioma",
            "acabado",
            name="uq_cartas_identity_tuple",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # === Identity tuple (requerido + unique compuesto) ===
    set_codigo: Mapped[str] = mapped_column(String(50), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    edicion: Mapped[Edicion] = mapped_column(
        Enum(
            Edicion, name="edicion_enum", values_callable=lambda e: [v.value for v in e]
        ),
        nullable=False,
    )
    idioma: Mapped[IdiomaCarta] = mapped_column(
        Enum(
            IdiomaCarta,
            name="idioma_carta_enum",
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
    )
    acabado: Mapped[Acabado] = mapped_column(
        Enum(
            Acabado, name="acabado_enum", values_callable=lambda e: [v.value for v in e]
        ),
        nullable=False,
    )

    # === Display (todo opcional, recomendado pero no requerido) ===
    nombre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rareza: Mapped[Rareza | None] = mapped_column(
        Enum(
            Rareza, name="rareza_enum", values_callable=lambda e: [v.value for v in e]
        ),
        nullable=True,
    )
    tipo: Mapped[TipoPokemon | None] = mapped_column(
        Enum(
            TipoPokemon,
            name="tipo_pokemon_enum",
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=True,
    )
    hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ilustrador: Mapped[str | None] = mapped_column(String(100), nullable=True)
    anio_impresion: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # === Imágenes en Blob Storage (R8) ===
    url_imagen_frente: Mapped[str] = mapped_column(Text, nullable=False)
    clave_blob_frente: Mapped[str] = mapped_column(Text, nullable=False)
    url_imagen_reverso: Mapped[str | None] = mapped_column(Text, nullable=True)
    clave_blob_reverso: Mapped[str | None] = mapped_column(Text, nullable=True)

    # === Auditoría ===
    creada_por_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id"),
        nullable=False,
    )
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
        return f"<Carta id={self.id} {self.set_codigo}-{self.numero}>"
