"""CLI para crear usuarios administrativos.

Uso:

```bash
# Interactivo (recomendado, contrasena no queda en historial)
python -m scripts.crear_admin --correo admin@ejemplo.com --alias root --rol superadmin

# No interactivo (CI o scripting)
PASSWORD=... python -m scripts.crear_admin --correo admin@ejemplo.com --alias root --rol admin --password-env PASSWORD
```

Los roles permitidos son `admin` y `superadmin`. Para crear submitters
usar el endpoint público `POST /api/v1/usuarios/registro`.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from getpass import getpass

from pokegrading.compartido.config import obtener_settings
from pokegrading.compartido.db import abrir_sesion
from pokegrading.compartido.seguridad import hashear_password
from pokegrading.usuarios import reglas
from pokegrading.usuarios.modelos import Usuario
from pokegrading.usuarios.repositorio import UsuarioRepositorio
from pokegrading.usuarios.tipos import Idioma, Pais, Rol

ROLES_PERMITIDOS = {Rol.ADMIN.value, Rol.SUPERADMIN.value}


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crea un usuario administrativo (admin o superadmin).",
    )
    parser.add_argument("--correo", required=True, help="Correo único del usuario.")
    parser.add_argument("--alias", required=True, help="Alias visible (3-50 chars).")
    parser.add_argument(
        "--rol",
        required=True,
        choices=sorted(ROLES_PERMITIDOS),
        help="Rol a asignar.",
    )
    parser.add_argument(
        "--pais",
        default=Pais.CR.value,
        choices=[p.value for p in Pais],
        help="País de residencia (default: CR).",
    )
    parser.add_argument(
        "--idioma",
        default=Idioma.ES.value,
        choices=[i.value for i in Idioma],
        help="Idioma preferido (default: es).",
    )
    parser.add_argument(
        "--password-env",
        help=(
            "Nombre de variable de entorno que contiene la contraseña. "
            "Si se omite, se solicita interactivamente."
        ),
    )
    return parser


def _obtener_password(args: argparse.Namespace) -> str:
    """Obtiene la contraseña de env var o interactivamente."""
    if args.password_env:
        valor = os.environ.get(args.password_env)
        if not valor:
            print(
                f"ERROR: la variable de entorno '{args.password_env}' "
                f"está vacía o no definida.",
                file=sys.stderr,
            )
            sys.exit(1)
        return valor

    contrasena = getpass("Contraseña: ")
    confirma = getpass("Confirma contraseña: ")
    if contrasena != confirma:
        print("ERROR: las contraseñas no coinciden.", file=sys.stderr)
        sys.exit(1)
    return contrasena


async def _crear_usuario(args: argparse.Namespace, contrasena: str) -> Usuario:
    """Persiste el nuevo usuario administrativo."""
    # Validar contraseña con las mismas reglas de la US Registrar Cuenta
    reglas.validar_password(contrasena)

    correo_normalizado = args.correo.strip().lower()
    settings = obtener_settings()

    async with abrir_sesion() as sesion:
        repo = UsuarioRepositorio(sesion)
        existente = await repo.obtener_por_correo(correo_normalizado)
        if existente is not None:
            print(
                f"ERROR: ya existe un usuario con correo {correo_normalizado}.",
                file=sys.stderr,
            )
            sys.exit(1)

        ahora = datetime.now(UTC)
        nuevo = Usuario(
            correo=correo_normalizado,
            alias=args.alias.strip(),
            hash_password=hashear_password(contrasena),
            pais=Pais(args.pais),
            idioma_preferido=Idioma(args.idioma),
            rol=Rol(args.rol),
            disclosure_aceptado=True,
            disclosure_version=settings.disclosure_version,
            disclosure_aceptado_en=ahora,
        )
        await repo.guardar(nuevo)
        await sesion.commit()
        return nuevo


async def _main() -> int:
    args = _construir_parser().parse_args()
    contrasena = _obtener_password(args)
    usuario = await _crear_usuario(args, contrasena)
    print(
        f"Usuario {args.rol} creado: id={usuario.id} correo={usuario.correo}"
    )
    return 0


def main() -> None:
    """Entry point sincrónico para `python -m scripts.crear_admin`."""
    try:
        raise SystemExit(asyncio.run(_main()))
    except KeyboardInterrupt:
        print("\nInterrumpido.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
