"""Router del API B2B.

Prefijo: /api/b2b/v1
Versionado independiente del API interno (/api/v1/*) para permitir
evolución del contrato sin romper clientes existentes (US B2B, DA-04).

Autenticación: header X-Api-Key (no Bearer JWT — las tiendas usan API keys).

Manejo de errores: todos los rechazos usan el formato único definido en la US:
{
  "error": "codigo_estable",
  "mensaje": "texto legible",
  "campo": "...",          # opcional
  "carta_index": N,        # opcional
  "correlation_id": "...",
  "reintentar_en": "..."   # opcional, solo rate limit
}
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.schemas.b2b import LookupRequest, LookupResponse
from pokegrading.datos.db import obtener_sesion
from pokegrading.negocio.b2b.servicio import LookupB2BService

router = APIRouter(prefix="/api/b2b/v1", tags=["b2b"])


@router.post(
    "/catalogo/lookup",
    response_model=LookupResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar cobertura de catálogo (B2B)",
    description=(
        "Permite a una tienda (Customer B2B) consultar si PokéGrading reconoce "
        "una o varias cartas en su catálogo, antes de enviarlas a evaluación.\n\n"
        "**Autenticación:** header `X-Api-Key` con la API key de la tienda.\n\n"
        "**Idempotencia:** incluir `identificador_solicitud` en el body para que "
        "reintentos dentro de la ventana configurada reciban la misma respuesta "
        "sin recontabilizarse contra la cuota.\n\n"
        "**Rate limit:** calculado sobre cantidad de cartas consultadas por mes, "
        "no sobre cantidad de llamadas. Esta operación **no** consume cuota de evaluación."
    ),
)
async def lookup_catalogo(
    payload: LookupRequest,
    request: Request,
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
    x_api_key: Annotated[
        str,
        Header(
            alias="X-Api-Key",
            description="API key de la tienda (formato: pg_b2b_...).",
        ),
    ],
) -> LookupResponse:
    """Endpoint de lookup B2B.

    El header X-Api-Key identifica a la tienda. Se hashea con SHA-256
    y se compara contra el hash almacenado en BD (nunca la clave en claro).
    """
    correlation_id = getattr(request.state, "correlation_id", None)

    servicio = LookupB2BService(sesion)
    return await servicio.ejecutar(
        api_key=x_api_key,
        payload=payload,
        correlation_id=str(correlation_id) if correlation_id else None,
    )
