"""Aplicación FastAPI de PokéGrading.

Ensambla:
- Configuración (settings)
- Logging estructurado JSON
- Middleware de Correlation ID
- Handlers globales de error
- Routers de cada módulo

Sigue el patrón de monolito modular del ADR-001: un único proceso, módulos
internos por responsabilidad, comunicación interna por imports directos.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pokegrading.compartido.config import obtener_settings
from pokegrading.compartido.correlation import CorrelationIdMiddleware
from pokegrading.compartido.errores import registrar_handlers
from pokegrading.compartido.logging import configurar_logging, obtener_logger
from pokegrading.usuarios.router import router as usuarios_router

configurar_logging()
logger = obtener_logger(__name__)


def crear_app() -> FastAPI:
    """Construye la instancia de FastAPI con toda la configuración."""
    app = FastAPI(
        title="PokéGrading API",
        version="0.1.0",
        description=(
            "API de PokéGrading — Sprint 1: registro de cuentas. "
            "Plataforma de pre-grading de cartas Pokémon para LATAM."
        ),
    )

    app.add_middleware(CorrelationIdMiddleware)
    # CORS — restrictivo en prod, permisivo en dev para soportar Vite dev server.
    settings = obtener_settings()
    if settings.app_env == "dev":
        origenes_permitidos = ["http://localhost:5173", "http://127.0.0.1:5173"]
    else:
        # En prod estos serán los dominios reales del frontend desplegado.
        origenes_permitidos = []  # TODO: poblar en sprint de deploy

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes_permitidos,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-Id"],
    )
    registrar_handlers(app)

    @app.get("/health", tags=["meta"], summary="Health check")
    async def health() -> dict[str, str]:
        """Endpoint de salud para liveness/readiness probes."""
        return {"estado": "ok"}

    app.include_router(usuarios_router)

    logger.info("app_iniciada", version="0.1.0")
    return app


app = crear_app()
