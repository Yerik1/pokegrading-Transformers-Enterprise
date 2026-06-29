"""Jerarquía de excepciones de dominio y handlers globales.

Las excepciones de dominio se mapean a códigos HTTP en los handlers.
El código de la aplicación NUNCA captura `Exception` desnudo (V6 §4.1):
captura siempre la excepción de dominio específica o deja burbujear.

Mapa de códigos HTTP:
  400 Bad Request         → ErrorSolicitudInvalida  (input bien formado pero inutilizable)
  401 Unauthorized        → ErrorAutenticacion
  403 Forbidden           → ErrorAutorizacion
  404 Not Found           → ErrorNoEncontrado
  409 Conflict            → ErrorConflicto
  422 Unprocessable       → ErrorValidacion         (formato/estructura de input inválida)
  429 Too Many Requests   → ErrorRateLimit

Formato de respuesta de error (consistente con la US "Mensajes de error
específicos por campo"):

```json
{
  "error": "correo_duplicado",
  "mensaje": "Ya existe una cuenta con este correo.",
  "campo": "correo",
  "correlation_id": "..."
}
```
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

from pokegrading.compartido.logging import obtener_logger

logger = obtener_logger(__name__)


class ErrorDominio(Exception):
    """Excepción base del dominio.

    Attributes:
        codigo: identificador snake_case para el cliente (ej. `correo_duplicado`).
        mensaje: texto legible para el usuario final.
        campo: nombre del campo afectado, si aplica (ej. `correo`).
        contexto: datos adicionales para debugging (no expuestos al cliente).
    """

    http_status: int = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        codigo: str,
        mensaje: str,
        *,
        campo: str | None = None,
        contexto: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.campo = campo
        self.contexto = contexto or {}


class ErrorValidacion(ErrorDominio):
    """Validación de formato o estructura del input (HTTP 422).

    Usar cuando el input no cumple el esquema esperado: tipo incorrecto,
    campo requerido ausente, formato de imagen inválido, resolución
    insuficiente, IQ Score bajo. Son errores que Pydantic o las reglas
    de validación detectan antes de procesar el contenido.
    """

    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT


class ErrorSolicitudInvalida(ErrorDominio):
    """Input bien formado pero inutilizable para el procesamiento (HTTP 400).

    Usar cuando el input supera la validación de formato pero el sistema
    no puede procesarlo por razones de contenido: imagen donde no se puede
    aislar la carta del fondo, distorsión de perspectiva imposible de
    corregir, JSON semánticamente inválido aunque esté bien formado.

    La distinción respecto a ErrorValidacion (422):
      - 422: el input tiene problemas de estructura/formato/esquema.
      - 400: el input tiene estructura correcta pero el contenido no sirve.
    """

    http_status = status.HTTP_400_BAD_REQUEST


class ErrorConflicto(ErrorDominio):
    """Conflicto de estado (ej. correo ya existe)."""

    http_status = status.HTTP_409_CONFLICT


class ErrorRateLimit(ErrorDominio):
    """Cuota excedida — reintentar más tarde."""

    http_status = status.HTTP_429_TOO_MANY_REQUESTS


class ErrorNoEncontrado(ErrorDominio):
    """Recurso solicitado no existe."""

    http_status = status.HTTP_404_NOT_FOUND


class ErrorAutenticacion(ErrorDominio):
    """Falla de autenticación."""

    http_status = status.HTTP_401_UNAUTHORIZED


class ErrorAutorizacion(ErrorDominio):
    """Usuario autenticado pero sin permiso."""

    http_status = status.HTTP_403_FORBIDDEN


def _payload_error(exc: ErrorDominio, correlation_id: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": exc.codigo,
        "mensaje": exc.mensaje,
    }
    if exc.campo is not None:
        payload["campo"] = exc.campo
    if correlation_id is not None:
        payload["correlation_id"] = correlation_id
    if exc.codigo == "cuota_mensual_excedida" and "reintentar_en" in exc.contexto:
        payload["reintentar_en"] = exc.contexto["reintentar_en"]
    return payload


def registrar_handlers(app: FastAPI) -> None:
    """Registra los exception handlers globales en la app FastAPI."""

    @app.exception_handler(ErrorDominio)
    async def _manejar_error_dominio(
        request: Request, exc: ErrorDominio
    ) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        logger.info(
            "error_dominio",
            codigo=exc.codigo,
            campo=exc.campo,
            contexto=exc.contexto,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=_payload_error(exc, correlation_id),
        )

    @app.exception_handler(RequestValidationError)
    async def _manejar_validacion_pydantic(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Errores de Pydantic v2 → primer error en formato canónico de dominio."""
        correlation_id = getattr(request.state, "correlation_id", None)
        primer_error = exc.errors()[0] if exc.errors() else {}
        loc = primer_error.get("loc", [])
        campo = str(loc[-1]) if loc else None
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": "validacion_invalida",
                "mensaje": primer_error.get("msg", "Datos de entrada inválidos."),
                "campo": campo,
                "correlation_id": correlation_id,
                "detalles": exc.errors(),
            },
        )
