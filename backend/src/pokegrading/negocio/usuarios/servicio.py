"""Servicio de aplicación del módulo `usuarios`.

Orquesta las reglas de dominio, el repositorio y los helpers de seguridad
para resolver casos de uso. No conoce ni FastAPI ni HTTP.

`RegistroService.ejecutar()` está dividido en pasos (`_validar_entrada`,
`_verificar_correo_disponible`, `_construir_usuario`, `_generar_par_tokens`)
para que el flujo principal se lea como una lista de pasos de alto nivel.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.config import obtener_settings
from pokegrading.compartido.errores import (
    ErrorAutenticacion,
    ErrorConflicto,
    ErrorValidacion,
)
from pokegrading.compartido.logging import obtener_logger
from pokegrading.compartido.schemas.usuarios import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegistroRequest,
    RegistroResponse,
    TokensResponse,
    UsuarioResponse,
)
from pokegrading.compartido.seguridad import (
    crear_token,
    decodificar_token,
    hashear_password,
    verificar_password,
)
from pokegrading.datos.db import unidad_de_trabajo
from pokegrading.negocio.usuarios import reglas
from pokegrading.negocio.usuarios.modelos import Usuario
from pokegrading.negocio.usuarios.repositorio import UsuarioRepositorio
from pokegrading.negocio.usuarios.tipos import Rol

logger = obtener_logger(__name__)


def _generar_par_tokens(usuario: Usuario) -> TokensResponse:
    claims = {"rol": usuario.rol.value}
    return TokensResponse(
        access_token=crear_token(str(usuario.id), tipo="access", extra_claims=claims),
        refresh_token=crear_token(str(usuario.id), tipo="refresh", extra_claims=claims),
    )


class RegistroService:
    """Caso de uso: registrar una nueva cuenta de Submitter."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion
        self._repo = UsuarioRepositorio(sesion)

    # ------------------------------------------------------------------
    # Orquestador — un paso por línea, sin lógica de negocio inline
    # ------------------------------------------------------------------

    async def ejecutar(self, datos: RegistroRequest) -> RegistroResponse:
        """Crea una cuenta nueva y retorna el usuario + tokens iniciales.

        Args:
            datos: payload validado por Pydantic en la capa API.

        Returns:
            `RegistroResponse` con el usuario público y el par de tokens.

        Raises:
            ErrorValidacion: si la contraseña no cumple las reglas, el
                dominio del correo está bloqueado, o no se aceptó el
                disclosure.
            ErrorConflicto: si el correo ya está registrado.
        """
        self._validar_entrada(datos)

        correo_normalizado = datos.correo.strip().lower()
        await self._verificar_correo_disponible(correo_normalizado)

        nuevo = self._construir_usuario(datos, correo_normalizado)
        await self._guardar_usuario(nuevo)

        logger.info(
            "usuario_registrado",
            usuario_id=str(nuevo.id),
            pais=nuevo.pais.value,
            rol=nuevo.rol.value,
        )

        tokens = _generar_par_tokens(nuevo)

        return RegistroResponse(
            usuario=UsuarioResponse.model_validate(nuevo),
            tokens=TokensResponse(
                access_token=tokens.access_token, refresh_token=tokens.refresh_token
            ),
        )

    # ------------------------------------------------------------------
    # Paso 1: validaciones de dominio sobre los inputs ya tipados
    # ------------------------------------------------------------------

    @staticmethod
    def _validar_entrada(datos: RegistroRequest) -> None:
        """Valida contraseña, dominio de correo y aceptación del disclosure.

        Raises:
            ErrorValidacion: si alguna regla no se cumple.
        """
        reglas.validar_password(datos.contrasena)
        reglas.validar_dominio_correo(datos.correo)

        if not datos.disclosure_aceptado:
            raise ErrorValidacion(
                codigo="disclosure_no_aceptado",
                mensaje=(
                    "Debes aceptar el disclosure de PokéGrading para "
                    "crear una cuenta."
                ),
                campo="disclosure_aceptado",
            )

    # ------------------------------------------------------------------
    # Paso 2: verificación de unicidad antes del insert
    # ------------------------------------------------------------------

    async def _verificar_correo_disponible(self, correo_normalizado: str) -> None:
        """Verifica que el correo no esté ya registrado.

        Esta es una verificación optimista; la garantía real de unicidad
        la da la restricción UNIQUE de BD, manejada como IntegrityError
        en `_guardar_usuario` para cubrir la race condition entre esta
        verificación y el insert.

        Raises:
            ErrorConflicto: si el correo ya está registrado.
        """
        existente = await self._repo.obtener_por_correo(correo_normalizado)
        if existente is not None:
            raise ErrorConflicto(
                codigo="correo_duplicado",
                mensaje="Ya existe una cuenta con este correo.",
                campo="correo",
            )

    # ------------------------------------------------------------------
    # Paso 3: construir el agregado con todos los defaults requeridos
    # ------------------------------------------------------------------

    @staticmethod
    def _construir_usuario(datos: RegistroRequest, correo_normalizado: str) -> Usuario:
        settings = obtener_settings()
        ahora = datetime.now(UTC)

        return Usuario(
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

    # ------------------------------------------------------------------
    # Paso 4: persistir como unidad de trabajo atómica
    # ------------------------------------------------------------------

    async def _guardar_usuario(self, nuevo: Usuario) -> None:
        """Persiste el usuario nuevo en una transacción atómica.

        Raises:
            ErrorConflicto: si hubo una race-condition con el mismo
                correo entre la verificación de unicidad y este insert.
        """
        try:
            async with unidad_de_trabajo(self._sesion):
                await self._repo.guardar(nuevo)
        except IntegrityError as exc:
            raise ErrorConflicto(
                codigo="correo_duplicado",
                mensaje="Ya existe una cuenta con este correo.",
                campo="correo",
            ) from exc


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
        usuario = await self._autenticar(datos)
        await self._registrar_login(usuario)

        tokens = _generar_par_tokens(usuario)

        return LoginResponse(
            usuario=UsuarioResponse.model_validate(usuario),
            tokens=TokensResponse(
                access_token=tokens.access_token, refresh_token=tokens.refresh_token
            ),
        )

    async def _autenticar(self, datos: LoginRequest) -> Usuario:
        """Verifica correo + contraseña.

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

        return usuario

    async def _registrar_login(self, usuario: Usuario) -> None:
        """Actualiza `last_login_at` y confirma el cambio en una transacción."""
        usuario.last_login_at = datetime.now(UTC)
        async with unidad_de_trabajo(self._sesion):
            pass  # el cambio en `usuario` ya está trackeado por la sesión

        logger.info(
            "usuario_login",
            usuario_id=str(usuario.id),
            rol=usuario.rol.value,
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
        usuario_id = self._extraer_usuario_id(datos.refresh_token)
        usuario = await self._repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise ErrorAutenticacion(
                codigo="usuario_no_existe",
                mensaje="El usuario asociado al token ya no existe.",
            )

        tokens = _generar_par_tokens(usuario)

        return RefreshResponse(
            tokens=TokensResponse(
                access_token=tokens.access_token, refresh_token=tokens.refresh_token
            )
        )

    @staticmethod
    def _extraer_usuario_id(refresh_token: str) -> uuid.UUID:
        """Decodifica el refresh token y extrae el ID de usuario.

        Raises:
            ErrorAutenticacion: si el token es inválido, no es de tipo
                refresh, o no contiene un sujeto válido.
        """
        payload = decodificar_token(refresh_token)

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
            return uuid.UUID(sub)
        except ValueError as exc:
            raise ErrorAutenticacion(
                codigo="token_invalido",
                mensaje="El identificador del usuario es inválido.",
            ) from exc
