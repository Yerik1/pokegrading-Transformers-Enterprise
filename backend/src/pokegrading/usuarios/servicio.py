"""Servicio de aplicación del módulo `usuarios`.

Orquesta las reglas de dominio, el repositorio y los helpers de seguridad
para resolver casos de uso. No conoce ni FastAPI ni HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.config import obtener_settings
from pokegrading.compartido.errores import ErrorConflicto
from pokegrading.compartido.logging import obtener_logger
from pokegrading.compartido.seguridad import crear_token, hashear_password
from pokegrading.usuarios import reglas
from pokegrading.usuarios.modelos import Usuario
from pokegrading.usuarios.repositorio import UsuarioRepositorio
from pokegrading.usuarios.schemas import (
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
