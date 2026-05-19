"""Script de verificación de la conexión a Azure Blob Storage.

Uso:
    python -m scripts.verificar_azure

Hace una operación end-to-end contra Azure usando la connection string
del `.env`:
1. Lista los contenedores existentes.
2. Sube un blob de prueba al contenedor configurado.
3. Verifica que existe.
4. Lo elimina.

Si todo pasa, el setup de Fase 1B está OK y se puede pasar a Fase 2.
"""

from __future__ import annotations

import asyncio
import sys

from pokegrading.compartido.almacenamiento import AlmacenamientoAzureBlob
from pokegrading.compartido.config import obtener_settings

CLAVE_PRUEBA = "_verificar_azure/test.txt"
CONTENIDO_PRUEBA = b"PokeGrading Azure setup OK"


async def _main() -> int:
    settings = obtener_settings()

    if not settings.azure_storage_connection_string:
        print(
            "ERROR: AZURE_STORAGE_CONNECTION_STRING no esta configurada en .env",
            file=sys.stderr,
        )
        return 1

    print("Conectando a Azure Storage...")
    almacenamiento = AlmacenamientoAzureBlob(settings.azure_storage_connection_string)
    contenedor = settings.azure_blob_container_cartas

    try:
        # Sondear que el contenedor existe listando sus blobs
        print(f"Listando contenedor '{contenedor}'...")
        # Si el contenedor no existe, esta llamada va a fallar limpio
        async for _ in almacenamiento._client.get_container_client(  # noqa: SLF001
            contenedor
        ).list_blobs(results_per_page=1):
            break
        print(f"  Contenedor '{contenedor}' existe y es accesible.")

        # Subir
        print(f"Subiendo blob de prueba '{CLAVE_PRUEBA}'...")
        url = await almacenamiento.guardar(
            contenedor, CLAVE_PRUEBA, CONTENIDO_PRUEBA, "text/plain"
        )
        print(f"  URL: {url}")

        # Verificar existencia
        print("Verificando existencia...")
        existe = await almacenamiento.existe(contenedor, CLAVE_PRUEBA)
        assert existe, "El blob recien subido no se encontro al verificar."
        print("  OK.")

        # Limpiar
        print("Eliminando blob de prueba...")
        await almacenamiento.eliminar(contenedor, CLAVE_PRUEBA)
        existe_post = await almacenamiento.existe(contenedor, CLAVE_PRUEBA)
        assert not existe_post, "El blob no se elimino correctamente."
        print("  OK.")

    except Exception as exc:
        print(f"\nFALLO: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        print(
            "\nRevisa: (1) connection string correcta, (2) contenedor creado, "
            "(3) red disponible.",
            file=sys.stderr,
        )
        return 1
    finally:
        await almacenamiento.cerrar()

    print("\nAzure Blob Storage verificado correctamente.")
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(_main()))
    except KeyboardInterrupt:
        print("\nInterrumpido.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
