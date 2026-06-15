"""Schemas Pydantic v2 para la frontera HTTP del módulo `usuarios`.

Separados del modelo ORM: el modelo es la representación persistente,
los schemas son contratos de API. Esto permite versionar el contrato sin
tocar la base de datos.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from pokegrading.negocio.usuarios.tipos import Idioma, Pais, Rol


class RegistroRequest(BaseModel):
    """Payload de `POST /api/v1/usuarios/registro`."""

    correo: EmailStr = Field(
        description="Correo electrónico válido y único.",
        examples=["coleccionista@ejemplo.com"],
    )
    alias: str = Field(
        min_length=3,
        max_length=50,
        description="Nombre visible del usuario en la plataforma.",
        examples=["maestro_pokemon"],
    )
    contrasena: str = Field(
        min_length=1,
        max_length=128,
        description=(
            "Contraseña. Validada por las reglas de dominio "
            "(longitud, mayúscula, dígito)."
        ),
    )
    pais: Pais = Field(description="País de residencia (ISO 3166-1 alpha-2).")
    idioma_preferido: Idioma = Field(
        default=Idioma.ES,
        description="Idioma preferido para la interfaz (default: español).",
    )
    disclosure_aceptado: bool = Field(
        description=(
            "El usuario aceptó el disclosure de que PokéGrading es informativo "
            "y no sustituye PSA/BGS/CGC."
        ),
    )


class UsuarioResponse(BaseModel):
    """Representación pública de un usuario (sin hash de contraseña)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    correo: EmailStr
    alias: str
    pais: Pais
    idioma_preferido: Idioma
    rol: Rol
    created_at: datetime


class TokensResponse(BaseModel):
    """Par de tokens entregados tras un registro o login exitoso."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegistroResponse(BaseModel):
    """Respuesta de `POST /api/v1/usuarios/registro`."""

    usuario: UsuarioResponse
    tokens: TokensResponse


class LoginRequest(BaseModel):
    """Payload de `POST /api/v1/auth/login`."""

    correo: EmailStr = Field(description="Correo registrado.")
    contrasena: str = Field(
        min_length=1,
        max_length=128,
        description="Contraseña en texto plano (se compara contra el hash).",
    )


class LoginResponse(BaseModel):
    """Respuesta de un login exitoso."""

    usuario: UsuarioResponse
    tokens: TokensResponse


class RefreshRequest(BaseModel):
    """Payload de `POST /api/v1/auth/refresh`."""

    refresh_token: str = Field(min_length=10)


class RefreshResponse(BaseModel):
    """Respuesta de un refresh exitoso: nuevo par de tokens."""

    tokens: TokensResponse
