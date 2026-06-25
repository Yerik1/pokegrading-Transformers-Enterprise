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

Cada paso de `ejecutar()` está extraído a su propio método privado
(`_autenticar`, `verificar_idempotencia`, `verificar_rate_limit`,
`_persistir_resultado`) para que el método orquestador se lea como una
lista de pasos de alto nivel y cada paso sea testeable y modificable
de forma aislada.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.errores import (
    ErrorAutenticacion,
)
from pokegrading.compartido.idempotencia import verificar_idempotencia
from pokegrading.compartido.logging import obtener_logger
from pokegrading.compartido.schemas.b2b import (
    AtributosCartaB2B,
    CartaConsultaItem,
    LookupRequest,
    LookupResponse,
    ResultadoCartaB2B,
)
from pokegrading.datos.db import unidad_de_trabajo
from pokegrading.negocio.b2b.modelos import B2BCuenta
from pokegrading.negocio.b2b.repositorio import B2BRepositorio
from pokegrading.negocio.b2b.seguridad import hashear_api_key, verificar_rate_limit
from pokegrading.negocio.catalogo.modelos import Carta
from pokegrading.negocio.catalogo.tipos import Acabado, Edicion, IdiomaCarta

logger = obtener_logger(__name__)


class LookupB2BService:
    """Caso de uso: consultar cobertura de catálogo por API B2B."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion
        self._repo = B2BRepositorio(sesion)

    # ------------------------------------------------------------------
    # Orquestador — un paso por línea, sin lógica de negocio inline
    # ------------------------------------------------------------------

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
        cuenta = await self._autenticar(api_key, correlation_id)

        respuesta_cacheada = await verificar_idempotencia(
            cuenta, payload, correlation_id, self._sesion
        )
        if respuesta_cacheada is not None:
            return respuesta_cacheada

        ahora = datetime.now(UTC)
        cartas_solicitadas = len(payload.cartas)
        await verificar_rate_limit(
            cuenta, cartas_solicitadas, ahora, correlation_id, self._sesion
        )

        resultados = await self._resolver_cartas(payload.cartas)
        respuesta = self._construir_respuesta(resultados, ahora, correlation_id)

        await self._persistir_resultado(
            cuenta, payload, cartas_solicitadas, ahora, correlation_id, respuesta
        )

        return respuesta

    # ------------------------------------------------------------------
    # Paso 1-2: autenticación + estado de cuenta
    # ------------------------------------------------------------------

    async def _autenticar(self, api_key: str, correlation_id: str | None) -> B2BCuenta:
        """Valida la API key y el estado de la cuenta (activa, no suspendida).

        Raises:
            ErrorAutenticacion: API key inválida o cuenta suspendida.
        """
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

        return cuenta

    # ------------------------------------------------------------------
    # Paso 3: idempotencia (verficar compartidos.idempotencia)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Paso 4: rate limiting (verificar seguridad.verificar_rate_limit)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Paso 5: construir la respuesta consolidada
    # ------------------------------------------------------------------

    @staticmethod
    def _construir_respuesta(
        resultados: list[ResultadoCartaB2B],
        ahora: datetime,
        correlation_id: str | None,
    ) -> LookupResponse:
        return LookupResponse(
            resultados=resultados,
            generado_en=ahora,
            es_reintento=False,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Paso 6-7: auditoría + rate limit como unidad de trabajo atómica
    # ------------------------------------------------------------------

    async def _persistir_resultado(
        self,
        cuenta: B2BCuenta,
        payload: LookupRequest,
        cartas_solicitadas: int,
        ahora: datetime,
        correlation_id: str | None,
        respuesta: LookupResponse,
    ) -> None:
        """Registra la auditoría e incrementa el rate limit en una sola
        transacción atómica.

        Ambas escrituras deben confirmarse juntas: un registro de
        auditoría sin su incremento de cuota correspondiente (o
        viceversa) dejaría el conteo de cuota desincronizado del
        historial real de consultas servidas.
        """
        respuesta_json = respuesta.model_dump_json()

        async with unidad_de_trabajo(self._sesion):
            await self._repo.registrar_consulta(
                cuenta_id=cuenta.id,
                idempotency_key=payload.identificador_solicitud,
                total_cartas=cartas_solicitadas,
                correlation_id=correlation_id,
                respuesta_json=respuesta_json,
                es_reintento=False,
            )
            await self._repo.incrementar_cartas_consultadas(
                cuenta_id=cuenta.id,
                anio=ahora.year,
                mes=ahora.month,
                cantidad=cartas_solicitadas,
            )

        logger.info(
            "b2b_lookup_completado",
            cuenta_id=str(cuenta.id),
            total_cartas=cartas_solicitadas,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Resolución de cartas individuales (ya estaba modularizado)
    # ------------------------------------------------------------------

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
        opcionales_o_error = self._validar_opcionales_canonicos(idx, carta)
        if isinstance(opcionales_o_error, ResultadoCartaB2B):
            return opcionales_o_error
        edicion_valida, idioma_valido, acabado_valido = opcionales_o_error

        coincidencias = await self._buscar_en_catalogo(
            carta, edicion_valida, idioma_valido, acabado_valido
        )
        return self._a_resultado_segun_coincidencias(idx, coincidencias)

    @staticmethod
    def _validar_opcionales_canonicos(
        idx: int, carta: CartaConsultaItem
    ) -> ResultadoCartaB2B | tuple[Edicion | None, IdiomaCarta | None, Acabado | None]:
        """Valida edicion/idioma/acabado contra sus enums canónicos.

        Returns:
            Tupla (edicion, idioma, acabado) si todos los opcionales
            presentes son válidos, o un ResultadoCartaB2B de error si
            alguno no lo es.
        """
        campos_a_validar = (
            ("edicion", carta.edicion, Edicion),
            ("idioma", carta.idioma, IdiomaCarta),
            ("acabado", carta.acabado, Acabado),
        )

        valores: dict[str, object] = {}
        for nombre_campo, valor_crudo, enum_cls in campos_a_validar:
            if valor_crudo is None:
                valores[nombre_campo] = None
                continue
            try:
                valores[nombre_campo] = enum_cls(valor_crudo)
            except ValueError:
                return ResultadoCartaB2B(
                    index=idx,
                    estado="parametros_invalidos",
                    motivo=(
                        f"Valor de '{nombre_campo}' no reconocido: '{valor_crudo}'. "
                        f"Valores válidos: {[e.value for e in enum_cls]}."
                    ),
                    campo=nombre_campo,
                )

        return valores["edicion"], valores["idioma"], valores["acabado"]

    async def _buscar_en_catalogo(
        self,
        carta: CartaConsultaItem,
        edicion: Edicion | None,
        idioma: IdiomaCarta | None,
        acabado: Acabado | None,
    ) -> list[Carta]:
        """Busca coincidencias en el catálogo por identity tuple,
        en orden estable por carta_id.
        """
        condiciones = [
            Carta.set_codigo == carta.set_codigo,
            Carta.numero == carta.numero,
        ]
        if edicion is not None:
            condiciones.append(Carta.edicion == edicion)
        if idioma is not None:
            condiciones.append(Carta.idioma == idioma)
        if acabado is not None:
            condiciones.append(Carta.acabado == acabado)

        stmt = select(Carta).where(and_(*condiciones)).order_by(Carta.id)
        resultado = await self._sesion.execute(stmt)
        return list(resultado.scalars().all())

    def _a_resultado_segun_coincidencias(
        self, idx: int, coincidencias: list[Carta]
    ) -> ResultadoCartaB2B:
        """Traduce la cantidad de coincidencias al estado correspondiente."""
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
