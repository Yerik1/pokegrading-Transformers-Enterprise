"""Servicio de identificación de cartas — búsqueda rápida."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.catalogo.modelos import Carta
from pokegrading.catalogo.reglas import TAMANO_MAXIMO_BYTES
from pokegrading.compartido.errores import ErrorValidacion
from pokegrading.compartido.logging import obtener_logger
from pokegrading.identificacion.algoritmo import (
    UMBRAL_ACEPTACION_AUTO,
    buscar_candidatos,
    calcular_phash,
)
from pokegrading.identificacion.schemas import (
    BusquedaRapidaResponse,
    CandidatoResponse,
)

logger = obtener_logger(__name__)


class BusquedaRapidaService:
    """Caso de uso: identificar carta por búsqueda rápida de phash."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def ejecutar(
        self,
        imagen_frente: bytes,
    ) -> BusquedaRapidaResponse:
        """Ejecuta la búsqueda rápida contra el catálogo.

        Args:
            imagen_frente: bytes de la imagen del frente de la carta.

        Returns:
            BusquedaRapidaResponse con candidatos y flags de escalado.

        Raises:
            ErrorValidacion: si la imagen no se puede procesar para phash.
        """
        # 1. Validar imagen antes de procesar
        if len(imagen_frente) == 0:
            raise ErrorValidacion(
                codigo="imagen_vacia",
                mensaje="El archivo de imagen está vacío.",
                campo="imagen_frente",
            )
        if len(imagen_frente) > TAMANO_MAXIMO_BYTES:
            raise ErrorValidacion(
                codigo="imagen_demasiado_grande",
                mensaje="La imagen excede el tamaño máximo de 10 MB.",
                campo="imagen_frente",
            )

        # 2. Calcular phash de la imagen recibida
        try:
            phash_consulta = calcular_phash(imagen_frente)
        except Exception as exc:
            raise ErrorValidacion(
                codigo="imagen_no_identificable",
                mensaje=(
                    "La imagen no permite identificación visual. "
                    "Intentá con mejor iluminación o encuadre."
                ),
                campo="imagen_frente",
            ) from exc

        # 2. Obtener entradas del catálogo que tienen phash calculado
        stmt = select(
            Carta.id,
            Carta.set_codigo,
            Carta.numero,
            Carta.nombre,
            Carta.phash_frente,
        ).where(Carta.phash_frente.is_not(None))

        resultado = await self._sesion.execute(stmt)
        filas = resultado.fetchall()

        if not filas:
            logger.info("catalogo_sin_phashes", total_cartas=0)
            return BusquedaRapidaResponse(
                candidatos=[],
                escala_a_especializada=True,
                deriva_a_manual=False,
                umbral_usado=UMBRAL_ACEPTACION_AUTO,
            )

        entradas = [
            {
                "carta_id": str(fila.id),
                "set_codigo": fila.set_codigo,
                "numero": fila.numero,
                "nombre": fila.nombre,
                "phash_frente": fila.phash_frente,
            }
            for fila in filas
        ]

        # 3. Buscar candidatos
        candidatos = buscar_candidatos(phash_consulta, entradas)

        # 4. Determinar flags de escalado
        tiene_candidato_aceptado = any(c.aceptado_automaticamente for c in candidatos)
        escala_a_especializada = len(candidatos) > 0 and not tiene_candidato_aceptado
        deriva_a_manual = len(candidatos) == 0

        return BusquedaRapidaResponse(
            candidatos=[
                CandidatoResponse(
                    carta_id=c.carta_id,
                    set_codigo=c.set_codigo,
                    numero=c.numero,
                    nombre=c.nombre,
                    confianza=c.confianza,
                    aceptado_automaticamente=c.aceptado_automaticamente,
                )
                for c in candidatos
            ],
            escala_a_especializada=escala_a_especializada,
            deriva_a_manual=deriva_a_manual,
            umbral_usado=UMBRAL_ACEPTACION_AUTO,
        )
