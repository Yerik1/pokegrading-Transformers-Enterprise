"""agregar superadmin al rol_enum

Revision ID: 0002_agregar_superadmin
Revises: 0001_inicial_usuarios
Create Date: 2026-05-18

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_agregar_superadmin"
down_revision: Union[str, None] = "0001_inicial_usuarios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE no puede correr dentro de una transacción en
    # versiones viejas de Postgres. `autocommit_block` desactiva el
    # transaction wrapping de Alembic para este bloque.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE rol_enum ADD VALUE IF NOT EXISTS 'superadmin'")


def downgrade() -> None:
    # PostgreSQL no soporta `DROP VALUE` de un enum nativamente.
    # Para revertir habría que: 1) crear nuevo tipo sin el valor, 2) migrar
    # la columna al nuevo tipo, 3) borrar el viejo. Es operación destructiva
    # que no debería pasar por un downgrade automático. Si fuera necesario
    # revertir, hacerlo en una migración ad-hoc explícita.
    pass
