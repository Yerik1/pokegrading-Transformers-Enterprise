"""Helpers de seguridad: hashing de contraseñas y JWT.

Decisiones (V6, SP8):
- Hashing: `bcrypt` directo (cost 12). Se truncan passwords a 72 bytes
  para respetar el límite del algoritmo (consistente con la práctica
  estándar; ya validamos longitud razonable en `reglas.validar_password`).
- JWT: `HS256` con secret de Key Vault en prod; access 15min, refresh 7 días.

Las contraseñas en claro NUNCA se loguean ni se devuelven al cliente.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from pokegrading.compartido.config import obtener_settings
from pokegrading.compartido.errores import ErrorAutenticacion

# Cost factor de bcrypt. 12 es el default seguro actual; balance entre
# resistencia a brute-force y latencia perceptible al usuario (~250ms).
_BCRYPT_ROUNDS: int = 12

# Límite del algoritmo bcrypt. Passwords más largas se truncan; esto es
# práctica estándar y compatible con todas las implementaciones.
_BCRYPT_MAX_BYTES: int = 72


def _truncar(plano: str) -> bytes:
    """Codifica a UTF-8 y trunca a 72 bytes preservando límites de caracter."""
    bytes_plano = plano.encode("utf-8")
    return bytes_plano[:_BCRYPT_MAX_BYTES]


def hashear_password(plano: str) -> str:
    """Genera el hash bcrypt de una contraseña en texto claro.

    Args:
        plano: contraseña en texto plano.

    Returns:
        Hash bcrypt (incluye salt y cost factor) como string ASCII.
    """
    hashed_bytes = bcrypt.hashpw(_truncar(plano), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
    return hashed_bytes.decode("ascii")


def verificar_password(plano: str, hashed: str) -> bool:
    """Verifica si una contraseña coincide con su hash.

    Args:
        plano: contraseña ingresada por el usuario.
        hashed: hash almacenado.

    Returns:
        True si coincide, False en caso contrario.
    """
    try:
        return bcrypt.checkpw(_truncar(plano), hashed.encode("ascii"))
    except ValueError:
        return False


TipoToken = Literal["access", "refresh"]


def crear_token(
    sub: str,
    *,
    tipo: TipoToken,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Crea un JWT firmado con el secret configurado.

    Args:
        sub: identificador del sujeto (usualmente el `id` del usuario).
        tipo: `"access"` o `"refresh"`.
        extra_claims: claims adicionales a incluir (ej. rol).

    Returns:
        JWT serializado.
    """
    settings = obtener_settings()
    ahora = datetime.now(timezone.utc)

    expira_en = (
        timedelta(minutes=settings.jwt_access_minutes)
        if tipo == "access"
        else timedelta(days=settings.jwt_refresh_days)
    )

    payload: dict[str, Any] = {
        "sub": sub,
        "tipo": tipo,
        "iat": ahora,
        "exp": ahora + expira_en,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decodificar_token(token: str) -> dict[str, Any]:
    """Decodifica y valida un JWT.

    Args:
        token: JWT recibido (sin el prefijo `Bearer `).

    Returns:
        Payload del token.

    Raises:
        ErrorAutenticacion: token inválido, expirado o mal formado.
    """
    settings = obtener_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise ErrorAutenticacion(
            codigo="token_expirado",
            mensaje="El token ha expirado.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise ErrorAutenticacion(
            codigo="token_invalido",
            mensaje="El token es inválido.",
        ) from exc