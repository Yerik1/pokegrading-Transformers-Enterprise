"""Helpers de seguridad para el módulo B2B.

La API key se maneja siguiendo el diseño de datos sensibles (DA-12, SP8):
1. Al crear una cuenta, se genera una API key aleatoria de 32 bytes (256 bits).
2. Solo se almacena su hash SHA-256. La clave en claro solo se muestra una vez
   al crear la cuenta y NUNCA se guarda ni se loguea.
3. Para autenticar, el cliente envía la API key; el sistema la hashea y compara
   contra el hash almacenado.
4. El prefijo (primeros 8 chars) se guarda para mostrar en dashboards.

Formato de la API key: pg_b2b_<32 bytes en hex> (64 chars hex + prefijo)
Ejemplo: pg_b2b_a3f9c2e1d4b7...  (identificable y no confundible con otros tokens)
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.errores import ErrorAutorizacion
from pokegrading.compartido.logging import obtener_logger
from pokegrading.negocio.b2b.modelos import B2BCuenta
from pokegrading.negocio.b2b.repositorio import B2BRepositorio

logger = obtener_logger(__name__)

_PREFIJO_API_KEY = "pg_b2b_"
_BYTES_SECRETO = 32  # 256 bits de entropía
# Código de error estable para rate limit (US: "informando cuándo reintentar")
_CODIGO_RATE_LIMIT = "cuota_mensual_excedida"


def generar_api_key() -> str:
    """Genera una API key segura para una cuenta B2B nueva.

    Returns:
        API key en claro. Solo se devuelve al crear la cuenta —
        NUNCA vuelve a estar disponible después.
    """
    secreto = secrets.token_hex(_BYTES_SECRETO)
    return f"{_PREFIJO_API_KEY}{secreto}"


def hashear_api_key(api_key: str) -> str:
    """Calcula el SHA-256 de una API key para almacenamiento seguro.

    Args:
        api_key: clave en claro (con prefijo pg_b2b_).

    Returns:
        Hash hexadecimal de 64 caracteres (SHA-256).
    """
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def extraer_prefijo(api_key: str) -> str:
    """Extrae los primeros 8 caracteres después del prefijo para dashboards.

    Permite identificar qué clave se está usando sin exponer el valor real.

    Args:
        api_key: clave en claro.

    Returns:
        Prefijo de 8 chars (del secreto, no del 'pg_b2b_').
    """
    secreto = api_key.removeprefix(_PREFIJO_API_KEY)
    return secreto[:8]


async def verificar_rate_limit(
    cuenta: B2BCuenta,
    cartas_solicitadas: int,
    ahora: datetime,
    correlation_id: str | None,
    sesion: AsyncSession,
) -> None:
    """Verifica que la cuenta no exceda su cuota mensual de cartas.

    Raises:
        ErrorAutorizacion: si la cuota mensual sería excedida.
    """
    _repo = B2BRepositorio(sesion)
    consumido = await _repo.obtener_cartas_consultadas_mes(
        cuenta_id=cuenta.id,
        anio=ahora.year,
        mes=ahora.month,
    )

    if consumido + cartas_solicitadas <= cuenta.limite_cartas_mes:
        return

    reintentar = _inicio_proximo_mes(ahora)

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


@staticmethod
def _inicio_proximo_mes(ahora: datetime) -> datetime:
    """Calcula el primer instante del mes calendario siguiente."""
    if ahora.month == 12:
        return ahora.replace(
            year=ahora.year + 1,
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    return ahora.replace(
        month=ahora.month + 1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
