"""Servicio de aplicación B2B: lookup de cobertura de catálogo.

Orquesta en este orden:
1. Autenticación de la API key (hash SHA-256 contra BD)
2. Verificación de estado de la cuenta (activa, no suspendida)
3. Idempotencia: si hay identificador_solicitud y ya existe dentro de la
   ventana, devuelve la respuesta original sin reprocesar ni recontabilizar.
4. Rate limiting: verifica que la cuenta no haya excedido su cuota mensual
   de cartas. Si la excede, rechaza con 429 e indica cuándo reintentar.
5. Lookup de cada carta en el catálogo (solo lectura, no consume cuota de evaluación).
6. Registro en auditoría (append-only, DA-03).
7. Incremento del contador de rate limit (excluye reintentos idempotentes).

La consulta es de solo lectura sobre el catálogo y NUNCA expone evaluaciones
ni datos de otras tiendas.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.errores import (
    ErrorAutenticacion,
    ErrorAutorizacion,
)
from pokegrading.compartido.logging import obtener_logger
from pokegrading.compartido.schemas.b2b import (
    AtributosCartaB2B,
    CartaConsultaItem,
    LookupRequest,
    LookupResponse,
    ResultadoCartaB2B,
)
from pokegrading.negocio.b2b.repositorio import B2BRepositorio
from pokegrading.negocio.b2b.seguridad import hashear_api_key
from pokegrading.negocio.catalogo.modelos import Carta
from pokegrading.negocio.catalogo.tipos import Acabado, Edicion, IdiomaCarta

logger = obtener_logger(__name__)

# Código de error estable para rate limit (US: "informando cuándo reintentar")
_CODIGO_RATE_LIMIT = "cuota_mensual_excedida"


class LookupB2BService:
    """Caso de uso: consultar cobertura de catálogo por API B2B."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion
        self._repo = B2BRepositorio(sesion)

    async def ejecutar(
        self,
        api_key: str,
        payload: LookupRequest,
        correlation_id: str | None = None,
    ) -> LookupResponse:
        """Ejecuta el lookup completo con todas las validaciones.

        Args:
            api_key: clave enviada por la tienda en el header X-Api-Key.
            payload: body del request validado por Pydantic.
            correlation_id: ID de correlación del request (DA-06).

        Returns:
            LookupResponse con resultado por carta.

        Raises:
            ErrorAutenticacion: API key inválida, revocada o cuenta suspendida.
            ErrorValidacion: consulta vacía o malformada.
            ErrorAutorizacion: cuota mensual excedida (429 semántico).
        """

        # === 1. Autenticar API key ===
        api_key_hash = hashear_api_key(api_key)
        cuenta = await self._repo.obtener_cuenta_por_hash(api_key_hash)

        if cuenta is None or not cuenta.activa:
            logger.warning(
                "b2b_api_key_invalida",
                api_key_prefijo=api_key[:8] if len(api_key) >= 8 else "?",
                correlation_id=correlation_id,
            )
            raise ErrorAutenticacion(
                codigo="api_key_invalida",
                mensaje="La API key proporcionada es inválida o ha sido revocada.",
            )

        if cuenta.suspendida:
            logger.warning(
                "b2b_cuenta_suspendida",
                cuenta_id=str(cuenta.id),
                correlation_id=correlation_id,
            )
            raise ErrorAutenticacion(
                codigo="cuenta_b2b_suspendida",
                mensaje=(
                    f"La cuenta B2B está suspendida. "
                    f"Motivo: {cuenta.motivo_suspension or 'no especificado'}."
                ),
            )

        # === 2. Idempotencia ===
        if payload.identificador_solicitud:
            registro_previo = await self._repo.obtener_consulta_por_idempotency_key(
                cuenta_id=cuenta.id,
                idempotency_key=payload.identificador_solicitud,
                ventana_segundos=cuenta.ventana_idempotencia_segundos,
            )
            if registro_previo is not None:
                logger.info(
                    "b2b_reintento_idempotente",
                    cuenta_id=str(cuenta.id),
                    idempotency_key=payload.identificador_solicitud,
                    correlation_id=correlation_id,
                )
                respuesta = LookupResponse.model_validate_json(
                    registro_previo.respuesta_json
                )
                respuesta.es_reintento = True
                respuesta.correlation_id = correlation_id
                return respuesta

        # === 3. Rate limiting ===
        ahora = datetime.now(UTC)
        cartas_solicitadas = len(payload.cartas)
        consumido = await self._repo.obtener_cartas_consultadas_mes(
            cuenta_id=cuenta.id,
            anio=ahora.year,
            mes=ahora.month,
        )

        if consumido + cartas_solicitadas > cuenta.limite_cartas_mes:
            # Calcular cuándo reintentar: inicio del próximo mes
            if ahora.month == 12:
                reintentar = ahora.replace(
                    year=ahora.year + 1,
                    month=1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            else:
                reintentar = ahora.replace(
                    month=ahora.month + 1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )

            logger.warning(
                "b2b_rate_limit_excedido",
                cuenta_id=str(cuenta.id),
                consumido=consumido,
                solicitado=cartas_solicitadas,
                limite=cuenta.limite_cartas_mes,
                correlation_id=correlation_id,
            )
            raise ErrorAutorizacion(
                codigo=_CODIGO_RATE_LIMIT,
                mensaje=(
                    f"Cuota mensual excedida. "
                    f"Consumidas: {consumido}, límite: {cuenta.limite_cartas_mes}. "
                    f"Reintentar a partir de: {reintentar.isoformat()}."
                ),
                contexto={"reintentar_en": reintentar.isoformat()},
            )

        # === 4. Lookup de cartas ===
        resultados = await self._resolver_cartas(payload.cartas)

        # === 5. Construir respuesta ===
        respuesta = LookupResponse(
            resultados=resultados,
            generado_en=ahora,
            es_reintento=False,
            correlation_id=correlation_id,
        )
        respuesta_json = respuesta.model_dump_json()

        # === 6. Auditoría (append-only) ===
        await self._repo.registrar_consulta(
            cuenta_id=cuenta.id,
            idempotency_key=payload.identificador_solicitud,
            total_cartas=cartas_solicitadas,
            correlation_id=correlation_id,
            respuesta_json=respuesta_json,
            es_reintento=False,
        )

        # === 7. Incrementar rate limit (solo consultas nuevas, no reintentos) ===
        await self._repo.incrementar_cartas_consultadas(
            cuenta_id=cuenta.id,
            anio=ahora.year,
            mes=ahora.month,
            cantidad=cartas_solicitadas,
        )

        await self._sesion.commit()

        logger.info(
            "b2b_lookup_completado",
            cuenta_id=str(cuenta.id),
            total_cartas=cartas_solicitadas,
            correlation_id=correlation_id,
        )

        return respuesta

    async def _resolver_cartas(
        self, cartas: list[CartaConsultaItem]
    ) -> list[ResultadoCartaB2B]:
        """Resuelve el estado de cada carta contra el catálogo.

        Cada carta se procesa de forma independiente: si una trae parámetros
        inválidos, se marca como tal; las demás se siguen procesando (US B2B).
        """
        resultados: list[ResultadoCartaB2B] = []

        for idx, carta in enumerate(cartas):
            resultado = await self._resolver_carta(idx, carta)
            resultados.append(resultado)

        return resultados

    async def _resolver_carta(
        self, idx: int, carta: CartaConsultaItem
    ) -> ResultadoCartaB2B:
        """Resuelve una carta individual. Nunca lanza excepción — devuelve estado."""

        # --- Validar opcionales contra enums canónicos ---
        edicion_valida: Edicion | None = None
        if carta.edicion is not None:
            try:
                edicion_valida = Edicion(carta.edicion)
            except ValueError:
                return ResultadoCartaB2B(
                    index=idx,
                    estado="parametros_invalidos",
                    motivo=(
                        f"Valor de 'edicion' no reconocido: '{carta.edicion}'. "
                        f"Valores válidos: {[e.value for e in Edicion]}."
                    ),
                    campo="edicion",
                )

        idioma_valido: IdiomaCarta | None = None
        if carta.idioma is not None:
            try:
                idioma_valido = IdiomaCarta(carta.idioma)
            except ValueError:
                return ResultadoCartaB2B(
                    index=idx,
                    estado="parametros_invalidos",
                    motivo=(
                        f"Valor de 'idioma' no reconocido: '{carta.idioma}'. "
                        f"Valores válidos: {[i.value for i in IdiomaCarta]}."
                    ),
                    campo="idioma",
                )

        acabado_valido: Acabado | None = None
        if carta.acabado is not None:
            try:
                acabado_valido = Acabado(carta.acabado)
            except ValueError:
                return ResultadoCartaB2B(
                    index=idx,
                    estado="parametros_invalidos",
                    motivo=(
                        f"Valor de 'acabado' no reconocido: '{carta.acabado}'. "
                        f"Valores válidos: {[a.value for a in Acabado]}."
                    ),
                    campo="acabado",
                )

        # --- Construir query con los filtros disponibles ---
        condiciones = [
            Carta.set_codigo == carta.set_codigo,
            Carta.numero == carta.numero,
        ]
        if edicion_valida is not None:
            condiciones.append(Carta.edicion == edicion_valida)
        if idioma_valido is not None:
            condiciones.append(Carta.idioma == idioma_valido)
        if acabado_valido is not None:
            condiciones.append(Carta.acabado == acabado_valido)

        stmt = select(Carta).where(and_(*condiciones)).order_by(Carta.id)
        resultado = await self._sesion.execute(stmt)
        coincidencias = resultado.scalars().all()

        # --- Determinar estado ---
        if len(coincidencias) == 0:
            return ResultadoCartaB2B(index=idx, estado="no_cubierta")

        if len(coincidencias) == 1:
            return ResultadoCartaB2B(
                index=idx,
                estado="cubierta",
                carta=self._a_atributos(coincidencias[0]),
            )

        # Múltiples coincidencias — orden estable por carta_id (ya aplicado en query)
        return ResultadoCartaB2B(
            index=idx,
            estado="coincidencia_multiple",
            candidatos=[self._a_atributos(c) for c in coincidencias],
        )

    @staticmethod
    def _a_atributos(carta: Carta) -> AtributosCartaB2B:
        """Convierte una Carta ORM a los atributos públicos B2B."""
        return AtributosCartaB2B(
            carta_id=str(carta.id),
            set_codigo=carta.set_codigo,
            numero=carta.numero,
            edicion=carta.edicion.value,
            idioma=carta.idioma.value,
            acabado=carta.acabado.value,
            nombre=carta.nombre,
        )
