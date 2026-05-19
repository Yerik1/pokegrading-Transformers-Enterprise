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

from pokegrading.catalogo.schemas import CartaResponse, CrearCartaRequest
from pokegrading.catalogo.servicio import CrearCartaService
from pokegrading.compartido.almacenamiento import (
    IAlmacenamientoImagenes,
    obtener_almacenamiento,
)
from pokegrading.compartido.db import obtener_sesion
from pokegrading.compartido.errores import ErrorValidacion
from pokegrading.usuarios.dependencias import requerir_admin_o_superadmin
from pokegrading.usuarios.modelos import Usuario

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
    # 1) Parsear el JSON del campo `datos`
    try:
        datos_dict = json.loads(datos)
    except json.JSONDecodeError as exc:
        raise ErrorValidacion(
            codigo="datos_json_invalido",
            mensaje="El campo 'datos' no contiene un JSON válido.",
            campo="datos",
        ) from exc

    # 2) Validar contra el schema Pydantic
    try:
        request = CrearCartaRequest.model_validate(datos_dict)
    except ValidationError as exc:
        primer_error = exc.errors()[0] if exc.errors() else {}
        loc = primer_error.get("loc", [])
        campo = str(loc[-1]) if loc else None
        raise ErrorValidacion(
            codigo="datos_invalidos",
            mensaje=primer_error.get("msg", "Datos de la carta inválidos."),
            campo=campo,
        ) from exc

    # 3) Leer los bytes de las imágenes
    bytes_frente = await imagen_frente.read()
    bytes_reverso: bytes | None = None
    if imagen_reverso is not None:
        bytes_reverso = await imagen_reverso.read()

    # 4) Delegar al servicio de aplicación
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
