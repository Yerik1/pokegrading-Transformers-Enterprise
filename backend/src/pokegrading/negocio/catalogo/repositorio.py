"""Repositorio de la entidad `Carta` (acceso a datos del catálogo)."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.negocio.catalogo.modelos import Carta
from pokegrading.negocio.catalogo.tipos import Acabado, Edicion, IdiomaCarta


class CartaRepositorio:
    """Acceso a la tabla `cartas_catalogo`."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_por_id(self, carta_id: uuid.UUID) -> Carta | None:
        return await self._sesion.get(Carta, carta_id)

    async def obtener_por_identity_tuple(
        self,
        *,
        set_codigo: str,
        numero: str,
        edicion: Edicion,
        idioma: IdiomaCarta,
        acabado: Acabado,
    ) -> Carta | None:
        """Busca una carta por los 5 campos que la identifican unívocamente."""
        stmt = select(Carta).where(
            and_(
                Carta.set_codigo == set_codigo,
                Carta.numero == numero,
                Carta.edicion == edicion,
                Carta.idioma == idioma,
                Carta.acabado == acabado,
            )
        )
        resultado = await self._sesion.execute(stmt)
        return resultado.scalar_one_or_none()

    async def guardar(self, carta: Carta) -> Carta:
        """Persiste una carta nueva. El commit lo hace el servicio."""
        self._sesion.add(carta)
        await self._sesion.flush()
        return carta
