"""Schemas Pydantic v2 para el API B2B.

Contrato del endpoint:
  POST /api/b2b/v1/catalogo/lookup

El versionado del API B2B es independiente del API interno (/api/v1/*).
Se usa /api/b2b/v1/ para permitir evolución del contrato sin romper clientes.

Formato de error único (US B2B):
{
  "error": "codigo_estable",
  "mensaje": "texto legible",
  "carta_index": 2,          # opcional: índice de la carta afectada
  "campo": "set_codigo",     # opcional: campo específico
  "correlation_id": "...",
  "reintentar_en": "..."     # opcional: ISO 8601, solo en rate limit
}
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class CartaConsultaItem(BaseModel):
    """Una carta dentro de una consulta B2B.

    Obligatorio: set_codigo + numero.
    Opcionales: edicion, idioma, acabado — sirven para desambiguar variantes.
    """

    set_codigo: str = Field(
        min_length=1,
        max_length=50,
        description="Código del set (ej. 'BASE1', 'SWSH01').",
    )
    numero: str = Field(
        min_length=1,
        max_length=20,
        description="Número de la carta dentro del set (ej. '4', '004/102').",
    )
    edicion: str | None = Field(
        default=None,
        description="Edición canónica ('1st_edition', 'unlimited', 'shadowless'). "
        "Opcional: desambigua entre variantes.",
    )
    idioma: str | None = Field(
        default=None,
        description="Idioma de la carta ('EN', 'JP', 'ES', …). Opcional.",
    )
    acabado: str | None = Field(
        default=None,
        description="Acabado físico ('holo', 'non_holo', …). Opcional.",
    )


class LookupRequest(BaseModel):
    """Payload del endpoint de lookup B2B.

    La tienda puede incluir un identificador_solicitud propio.
    Si llega el mismo identificador dentro de la ventana de idempotencia,
    el sistema devuelve exactamente la misma respuesta sin recontarla.
    """

    cartas: list[CartaConsultaItem] = Field(
        min_length=1,
        description="Lista de cartas a consultar. Mínimo 1.",
    )
    identificador_solicitud: str | None = Field(
        default=None,
        max_length=128,
        description=(
            "Identificador de solicitud propio de la tienda. "
            "Usado para idempotencia: reintentos con el mismo ID y dentro "
            "de la ventana configurada reciben la misma respuesta."
        ),
    )


# ---------------------------------------------------------------------------
# Response: por carta
# ---------------------------------------------------------------------------


class AtributosCartaB2B(BaseModel):
    """Atributos oficiales de una carta en el catálogo."""

    carta_id: str
    set_codigo: str
    numero: str
    edicion: str
    idioma: str
    acabado: str
    nombre: str | None = None


class ResultadoCartaB2B(BaseModel):
    """Resultado individual de una carta consultada.

    Estado posible:
    - cubierta: existe exactamente una coincidencia activa.
    - coincidencia_multiple: más de una carta coincide con los parámetros dados.
    - no_cubierta: no existe en el catálogo o está retirada.
    - parametros_invalidos: faltan obligatorios o un opcional fuera de los canónicos.
    """

    index: int = Field(description="Posición (0-based) de esta carta en el request.")
    estado: str = Field(
        description="'cubierta' | 'coincidencia_multiple' | 'no_cubierta' | 'parametros_invalidos'"
    )

    # Solo cuando estado == "cubierta"
    carta: AtributosCartaB2B | None = None

    # Solo cuando estado == "coincidencia_multiple"
    # Orden estable y reproducible (ordenado por carta_id)
    candidatos: list[AtributosCartaB2B] | None = None

    # Solo cuando estado == "parametros_invalidos"
    motivo: str | None = None
    campo: str | None = None


# ---------------------------------------------------------------------------
# Response: global
# ---------------------------------------------------------------------------


class LookupResponse(BaseModel):
    """Respuesta completa del endpoint de lookup B2B."""

    resultados: list[ResultadoCartaB2B]

    # Metadatos para caché condicional (DA-11: catálogo cambia poco)
    generado_en: datetime = Field(
        description="Timestamp UTC de generación. "
        "La tienda puede usar este valor para verificar si un resultado previo sigue vigente."
    )

    # Idempotencia: si es reintento, lo indicamos explícitamente
    es_reintento: bool = Field(
        default=False,
        description="True si esta respuesta fue servida desde caché de idempotencia.",
    )

    correlation_id: str | None = None
