"""CLI para crear una cuenta B2B (tienda / partner).

Crea el Usuario de servicio con rol B2B_SERVICE_ACCOUNT, la B2BCuenta
asociada y genera su API key. La clave se muestra UNA SOLA VEZ — no
queda registrada en BD ni en logs.

Uso:

```bash
# Interactivo (recomendado)
python -m scripts.crear_cuenta_b2b --tienda "Tienda Ejemplo" --correo tienda@ejemplo.com

# Con límite personalizado de cartas por mes
python -m scripts.crear_cuenta_b2b --tienda "Tienda VIP" --correo vip@ejemplo.com --limite 50000

# No interactivo (CI): contraseña por env var
PASSWORD=... python -m scripts.crear_cuenta_b2b \
    --tienda "Tienda CI" --correo ci@ejemplo.com --password-env PASSWORD
```
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from getpass import getpass

from pokegrading.compartido.config import obtener_settings
from pokegrading.datos.db import abrir_sesion
from pokegrading.compartido.seguridad import hashear_password
from pokegrading.negocio.b2b.seguridad import (
    extraer_prefijo,
    generar_api_key,
    hashear_api_key,
)
from pokegrading.negocio.b2b.modelos import B2BCuenta
from pokegrading.negocio.usuarios.modelos import Usuario
from pokegrading.negocio.usuarios.repositorio import UsuarioRepositorio
from pokegrading.negocio.usuarios.tipos import Idioma, Pais, Rol
from pokegrading.negocio.usuarios import reglas


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crea una cuenta B2B (tienda) con su API key.",
    )
    parser.add_argument(
        "--tienda",
        required=True,
        help="Nombre de la tienda (visible en dashboards y soporte).",
    )
    parser.add_argument(
        "--correo",
        required=True,
        help="Correo del usuario de servicio asociado a la cuenta.",
    )
    parser.add_argument(
        "--alias",
        default=None,
        help="Alias del usuario de servicio (default: mismo que --tienda).",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=10_000,
        help="Límite de cartas consultadas por mes (default: 10000).",
    )
    parser.add_argument(
        "--ventana-idempotencia",
        type=int,
        default=300,
        dest="ventana_idempotencia",
        help="Ventana de idempotencia en segundos (default: 300 = 5 min).",
    )
    parser.add_argument(
        "--pais",
        default=Pais.CR.value,
        choices=[p.value for p in Pais],
        help="País del usuario de servicio (default: CR).",
    )
    parser.add_argument(
        "--password-env",
        dest="password_env",
        help=(
            "Nombre de variable de entorno con la contraseña del usuario de servicio. "
            "Si se omite, se solicita interactivamente."
        ),
    )
    return parser


def _obtener_password(args: argparse.Namespace) -> str:
    """Obtiene la contraseña del usuario de servicio."""
    if args.password_env:
        valor = os.environ.get(args.password_env)
        if not valor:
            print(
                f"ERROR: la variable '{args.password_env}' está vacía o no definida.",
                file=sys.stderr,
            )
            sys.exit(1)
        return valor

    contrasena = getpass("Contraseña del usuario de servicio: ")
    confirma = getpass("Confirmar contraseña: ")
    if contrasena != confirma:
        print("ERROR: las contraseñas no coinciden.", file=sys.stderr)
        sys.exit(1)
    return contrasena


async def _crear_cuenta(args: argparse.Namespace, contrasena: str) -> tuple[B2BCuenta, str]:
    """Crea el Usuario B2B y la B2BCuenta en una sola transacción.

    Returns:
        (cuenta creada, api_key en claro)
    """
    reglas.validar_password(contrasena)

    correo_normalizado = args.correo.strip().lower()
    alias = (args.alias or args.tienda).strip()
    settings = obtener_settings()

    async with abrir_sesion() as sesion:
        # Verificar que el correo no esté en uso
        repo_usuarios = UsuarioRepositorio(sesion)
        existente = await repo_usuarios.obtener_por_correo(correo_normalizado)
        if existente is not None:
            print(
                f"ERROR: ya existe un usuario con correo '{correo_normalizado}'.",
                file=sys.stderr,
            )
            sys.exit(1)

        ahora = datetime.now(UTC)

        # Crear el usuario de servicio
        usuario = Usuario(
            correo=correo_normalizado,
            alias=alias,
            hash_password=hashear_password(contrasena),
            pais=Pais(args.pais),
            idioma_preferido=Idioma.ES,
            rol=Rol.B2B_SERVICE_ACCOUNT,
            disclosure_aceptado=True,
            disclosure_version=settings.disclosure_version,
            disclosure_aceptado_en=ahora,
        )
        sesion.add(usuario)
        await sesion.flush()  # obtener usuario.id antes de usarlo en B2BCuenta

        # Generar API key (en claro solo aquí, nunca más)
        api_key = generar_api_key()

        # Crear la cuenta B2B
        cuenta = B2BCuenta(
            nombre_tienda=args.tienda.strip(),
            api_key_hash=hashear_api_key(api_key),
            api_key_prefijo=extraer_prefijo(api_key),
            activa=True,
            suspendida=False,
            limite_cartas_mes=args.limite,
            ventana_idempotencia_segundos=args.ventana_idempotencia,
            usuario_id=usuario.id,
        )
        sesion.add(cuenta)
        await sesion.commit()

        return cuenta, api_key


async def _main() -> int:
    args = _construir_parser().parse_args()
    contrasena = _obtener_password(args)
    cuenta, api_key = await _crear_cuenta(args, contrasena)

    print("")
    print("  \033[32m✓ Cuenta B2B creada exitosamente\033[0m")
    print("")
    print(f"  \033[36mTienda       \033[0m {cuenta.nombre_tienda}")
    print(f"  \033[36mCuenta ID    \033[0m {cuenta.id}")
    print(f"  \033[36mLímite/mes   \033[0m {cuenta.limite_cartas_mes:,} cartas")
    print(f"  \033[36mPrefijo      \033[0m {cuenta.api_key_prefijo}")
    print("")
    print("  \033[33m⚠️  API KEY — guardala ahora, no se puede recuperar después:\033[0m")
    print(f"  \033[33m{api_key}\033[0m")
    print("")

    return 0


def main() -> None:
    """Entry point sincrónico para `python -m scripts.crear_cuenta_b2b`."""
    try:
        raise SystemExit(asyncio.run(_main()))
    except KeyboardInterrupt:
        print("\nInterrumpido.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()