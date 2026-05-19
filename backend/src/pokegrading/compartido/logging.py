"""Logging estructurado JSON con correlation ID (S2, DA-06).

Usa `structlog` para emitir logs en JSON. El `correlation_id` se inyecta
automáticamente desde el contexto de la request (ver `correlation.py`).

No usar `print()` ni `logging` directamente en código de aplicación;
usar `obtener_logger(__name__)`.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from pokegrading.compartido.config import obtener_settings


def configurar_logging() -> None:
    """Configura structlog + stdlib logging para emisión JSON.

    Llamar una vez al inicio de la aplicación.
    """
    settings = obtener_settings()
    nivel = getattr(logging, settings.log_level)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=nivel,
    )

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(nivel),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def obtener_logger(nombre: str) -> Any:
    """Devuelve un logger estructurado para el módulo dado.

    Args:
        nombre: típicamente `__name__` del módulo llamador.

    Returns:
        Logger structlog con el nombre vinculado.
    """
    return structlog.get_logger(nombre)
