from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.logging import obtener_logger
from pokegrading.compartido.schemas.b2b import LookupRequest, LookupResponse
from pokegrading.negocio.b2b.modelos import B2BCuenta
from pokegrading.negocio.b2b.repositorio import B2BRepositorio

logger = obtener_logger(__name__)


async def verificar_idempotencia(
    cuenta: B2BCuenta,
    payload: LookupRequest,
    correlation_id: str | None,
    sesion: AsyncSession,
) -> LookupResponse | None:
    """Si la consulta es un reintento dentro de la ventana, devuelve
    la respuesta original guardada. Si no, devuelve None y el flujo
    continúa normalmente.
    """
    if not payload.identificador_solicitud:
        return None

    _repo = B2BRepositorio(sesion)

    registro_previo = await _repo.obtener_consulta_por_idempotency_key(
        cuenta_id=cuenta.id,
        idempotency_key=payload.identificador_solicitud,
        ventana_segundos=cuenta.ventana_idempotencia_segundos,
    )
    if registro_previo is None:
        return None

    logger.info(
        "b2b_reintento_idempotente",
        cuenta_id=str(cuenta.id),
        idempotency_key=payload.identificador_solicitud,
        correlation_id=correlation_id,
    )
    respuesta = LookupResponse.model_validate_json(registro_previo.respuesta_json)
    respuesta.es_reintento = True
    respuesta.correlation_id = correlation_id
    return respuesta
