"""Router HTTP del módulo `catalogo`.

Endpoint principal: `POST /api/v1/catalogo/cartas` (multipart/form-data).
Solo accesible para usuarios con rol `admin` o `superadmin`.
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.almacenamiento import (
    IAlmacenamientoImagenes,
    obtener_almacenamiento,
)
from pokegrading.compartido.dependencias import requerir_admin_o_superadmin
from pokegrading.compartido.errores import ErrorValidacion
from pokegrading.compartido.schemas.catalogo import CartaResponse, CrearCartaRequest
from pokegrading.datos.db import obtener_sesion
from pokegrading.negocio.catalogo.servicio import CrearCartaService
from pokegrading.negocio.usuarios.modelos import Usuario

router = APIRouter(prefix="/api/v1/catalogo", tags=["catalogo"])


@router.post(
    "/cartas",
    response_model=CartaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar una carta al catálogo de referencia",
    description=(
        "Crea una entrada nueva en el catálogo. Requiere multipart/form-data con:\n\n"
        "- `datos`: JSON con los atributos de la carta (identity tuple obligatorio).\n"
        "- `imagen_frente`: archivo de imagen (requerido, JPEG o PNG, "
        "600×840 mín / 4000×6000 máx, ≤10 MB).\n"
        "- `imagen_reverso`: archivo opcional, mismos criterios.\n\n"
        "**Autorización:** Bearer token de usuario `admin` o `superadmin`."
    ),
)
async def agregar_carta_al_catalogo(
    datos: Annotated[
        str,
        Form(description="JSON con los campos de la carta. Ver CrearCartaRequest."),
    ],
    imagen_frente: Annotated[UploadFile, File(description="Imagen frontal requerida.")],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
    almacenamiento: Annotated[IAlmacenamientoImagenes, Depends(obtener_almacenamiento)],
    usuario_actual: Annotated[Usuario, Depends(requerir_admin_o_superadmin)],
    imagen_reverso: Annotated[
        UploadFile | None, File(description="Imagen del reverso (opcional).")
    ] = None,
) -> CartaResponse:
    """Endpoint POST que da de alta una carta. Cubre la US "Agregar carta al catálogo"."""
    request = _parsear_y_validar_datos(datos)
    bytes_frente, bytes_reverso = await _leer_imagenes(imagen_frente, imagen_reverso)

    servicio = CrearCartaService(sesion, almacenamiento)
    return await servicio.ejecutar(
        request,
        imagen_frente=bytes_frente,
        content_type_frente=imagen_frente.content_type or "application/octet-stream",
        imagen_reverso=bytes_reverso,
        content_type_reverso=(
            imagen_reverso.content_type if imagen_reverso is not None else None
        ),
        creada_por_id=usuario_actual.id,
    )


def _parsear_y_validar_datos(datos: str) -> CrearCartaRequest:
    """Parsea el campo `datos` (JSON embebido en multipart) y lo valida
    contra el schema Pydantic.

    Raises:
        ErrorValidacion: si el JSON es inválido o no cumple el schema.
    """
    try:
        datos_dict = json.loads(datos)
    except json.JSONDecodeError as exc:
        raise ErrorValidacion(
            codigo="datos_json_invalido",
            mensaje="El campo 'datos' no contiene un JSON válido.",
            campo="datos",
        ) from exc

    try:
        return CrearCartaRequest.model_validate(datos_dict)
    except ValidationError as exc:
        primer_error = exc.errors()[0] if exc.errors() else {}
        loc = primer_error.get("loc", [])
        campo = str(loc[-1]) if loc else None
        raise ErrorValidacion(
            codigo="datos_invalidos",
            mensaje=primer_error.get("msg", "Datos de la carta inválidos."),
            campo=campo,
        ) from exc


async def _leer_imagenes(
    imagen_frente: UploadFile, imagen_reverso: UploadFile | None
) -> tuple[bytes, bytes | None]:
    """Lee los bytes de las imágenes recibidas en el multipart."""
    bytes_frente = await imagen_frente.read()
    bytes_reverso = await imagen_reverso.read() if imagen_reverso is not None else None
    return bytes_frente, bytes_reverso
