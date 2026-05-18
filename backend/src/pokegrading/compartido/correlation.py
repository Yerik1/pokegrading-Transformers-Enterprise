"""Middleware de Correlation ID (S2, DA-06).

Cada request recibe un `correlation_id` único que se:
- Lee del header `X-Correlation-Id` si viene del cliente (idempotencia entre reintentos)
- O se autogenera con UUID4 si no
- Se inyecta en el contexto de `structlog` para que todos los logs lo incluyan
- Se devuelve en la respuesta como header `X-Correlation-Id`
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER_CORRELATION_ID = "X-Correlation-Id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Asigna y propaga un correlation ID por request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = request.headers.get(HEADER_CORRELATION_ID) or str(uuid.uuid4())

        # Estado disponible para handlers vía request.state.correlation_id
        request.state.correlation_id = correlation_id

        # Vincula el correlation_id al contexto de structlog para esta request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        try:
            respuesta = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        respuesta.headers[HEADER_CORRELATION_ID] = correlation_id
        return respuesta
