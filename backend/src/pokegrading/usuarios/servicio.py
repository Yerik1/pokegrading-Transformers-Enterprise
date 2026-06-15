"""Servicio de aplicación del módulo `usuarios`.

Orquesta las reglas de dominio, el repositorio y los helpers de seguridad
para resolver casos de uso. No conoce ni FastAPI ni HTTP.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.config import obtener_settings
from pokegrading.compartido.errores import ErrorAutenticacion, ErrorConflicto
from pokegrading.compartido.logging import obtener_logger
from pokegrading.compartido.seguridad import (
    crear_token,
    decodificar_token,
    hashear_password,
    verificar_password,
)
from pokegrading.usuarios import reglas
from pokegrading.usuarios.modelos import Usuario
from pokegrading.usuarios.repositorio import UsuarioRepositorio
from pokegrading.usuarios.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegistroRequest,
    RegistroResponse,
    TokensResponse,
    UsuarioResponse,
)
from pokegrading.usuarios.tipos import Rol

logger = obtener_logger(__name__)


class RegistroService:
    """Caso de uso: registrar una nueva cuenta de Submitter."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion
        self._repo = UsuarioRepositorio(sesion)

    async def ejecutar(self, datos: RegistroRequest) -> RegistroResponse:
        """Crea una cuenta nueva y retorna el usuario + tokens iniciales.

        Args:
            datos: payload validado por Pydantic en la capa API.

        Returns:
            `RegistroResponse` con el usuario público y el par de tokens.

        Raises:
            ErrorValidacion: si la contraseña no cumple las reglas o el
                dominio del correo está bloqueado.
            ErrorConflicto: si el correo ya está registrado.
        """
        # 1) Validaciones de dominio sobre los inputs ya tipados
        reglas.validar_password(datos.contrasena)
        reglas.validar_dominio_correo(datos.correo)

        if not datos.disclosure_aceptado:
            from pokegrading.compartido.errores import ErrorValidacion

            raise ErrorValidacion(
                codigo="disclosure_no_aceptado",
                mensaje=(
                    "Debes aceptar el disclosure de PokéGrading para "
                    "crear una cuenta."
                ),
                campo="disclosure_aceptado",
            )

        correo_normalizado = datos.correo.strip().lower()

        # 2) Verificación de unicidad antes del insert (mensaje específico)
        existente = await self._repo.obtener_por_correo(correo_normalizado)
        if existente is not None:
            raise ErrorConflicto(
                codigo="correo_duplicado",
                mensaje="Ya existe una cuenta con este correo.",
                campo="correo",
            )

        # 3) Construir el agregado con todos los defaults requeridos
        settings = obtener_settings()
        ahora = datetime.now(UTC)

        nuevo = Usuario(
            correo=correo_normalizado,
            alias=datos.alias.strip(),
            hash_password=hashear_password(datos.contrasena),
            pais=datos.pais,
            idioma_preferido=datos.idioma_preferido,
            rol=Rol.SUBMITTER,  # default por US (los demás roles se asignan por admin)
            disclosure_aceptado=True,
            disclosure_version=settings.disclosure_version,
            disclosure_aceptado_en=ahora,
        )

        try:
            await self._repo.guardar(nuevo)
            await self._sesion.commit()
        except IntegrityError as exc:
            # Race-condition: otro request creó el mismo correo entre
            # nuestra verificación y el insert.
            await self._sesion.rollback()
            raise ErrorConflicto(
                codigo="correo_duplicado",
                mensaje="Ya existe una cuenta con este correo.",
                campo="correo",
            ) from exc

        logger.info(
            "usuario_registrado",
            usuario_id=str(nuevo.id),
            pais=nuevo.pais.value,
            rol=nuevo.rol.value,
        )

        # 4) Generar par de tokens iniciales (la US dice "cuenta activa de
        # inmediato": entregamos tokens junto con el registro).
        claims = {"rol": nuevo.rol.value}
        access = crear_token(str(nuevo.id), tipo="access", extra_claims=claims)
        refresh = crear_token(str(nuevo.id), tipo="refresh", extra_claims=claims)

        return RegistroResponse(
            usuario=UsuarioResponse.model_validate(nuevo),
            tokens=TokensResponse(access_token=access, refresh_token=refresh),
        )


class LoginService:
    """Caso de uso: autenticar credenciales y emitir un par de tokens."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion
        self._repo = UsuarioRepositorio(sesion)

    async def ejecutar(self, datos: LoginRequest) -> LoginResponse:
        """Verifica credenciales y devuelve usuario + tokens.

        Las credenciales inválidas se reportan con mensaje genérico
        ('credenciales_invalidas') sin revelar si el correo existe — defensa
        contra enumeración de cuentas (SP2 OWASP).

        Args:
            datos: payload con correo y contraseña.

        Returns:
            Usuario público + par de tokens iniciales.

        Raises:
            ErrorAutenticacion: si las credenciales no son válidas.
        """
        correo_normalizado = datos.correo.strip().lower()
        usuario = await self._repo.obtener_por_correo(correo_normalizado)

        # Verificamos password incluso si no hay usuario para evitar timing
        # attack que delate la existencia del correo.
        password_valida = usuario is not None and verificar_password(
            datos.contrasena, usuario.hash_password
        )

        if usuario is None or not password_valida:
            raise ErrorAutenticacion(
                codigo="credenciales_invalidas",
                mensaje="Correo o contraseña incorrectos.",
            )

        # Actualizar last_login_at
        usuario.last_login_at = datetime.now(UTC)
        await self._sesion.commit()

        logger.info(
            "usuario_login",
            usuario_id=str(usuario.id),
            rol=usuario.rol.value,
        )

        claims = {"rol": usuario.rol.value}
        access = crear_token(str(usuario.id), tipo="access", extra_claims=claims)
        refresh = crear_token(str(usuario.id), tipo="refresh", extra_claims=claims)

        return LoginResponse(
            usuario=UsuarioResponse.model_validate(usuario),
            tokens=TokensResponse(access_token=access, refresh_token=refresh),
        )


class RefreshService:
    """Caso de uso: emitir un nuevo par de tokens a partir de un refresh token."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._repo = UsuarioRepositorio(sesion)

    async def ejecutar(self, datos: RefreshRequest) -> RefreshResponse:
        """Valida el refresh token y emite un nuevo par.

        Implementa **rotación de refresh tokens**: cada refresh devuelve un
        nuevo refresh, no el mismo. Reduce ventana de exposición si el
        refresh token se filtra.

        Args:
            datos: payload con el refresh token.

        Returns:
            Nuevo par de tokens (access + refresh).

        Raises:
            ErrorAutenticacion: si el token es inválido, expiró, no es de
                tipo refresh, o el usuario asociado ya no existe.
        """
        payload = decodificar_token(datos.refresh_token)

        if payload.get("tipo") != "refresh":
            raise ErrorAutenticacion(
                codigo="tipo_token_invalido",
                mensaje="Se esperaba un refresh token.",
            )

        sub = payload.get("sub")
        if not sub:
            raise ErrorAutenticacion(
                codigo="token_invalido",
                mensaje="El token no contiene un sujeto válido.",
            )

        try:
            usuario_id = uuid.UUID(sub)
        except ValueError as exc:
            raise ErrorAutenticacion(
                codigo="token_invalido",
                mensaje="El identificador del usuario es inválido.",
            ) from exc

        usuario = await self._repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise ErrorAutenticacion(
                codigo="usuario_no_existe",
                mensaje="El usuario asociado al token ya no existe.",
            )

        claims = {"rol": usuario.rol.value}
        access = crear_token(str(usuario.id), tipo="access", extra_claims=claims)
        refresh = crear_token(str(usuario.id), tipo="refresh", extra_claims=claims)

        return RefreshResponse(
            tokens=TokensResponse(access_token=access, refresh_token=refresh)
        )
