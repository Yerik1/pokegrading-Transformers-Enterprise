"""Tests del contrato `IAlmacenamientoImagenes`.

Verifica la implementación `AlmacenamientoEnMemoria` contra el contrato.
La implementación de Azure se valida manualmente con
`python -m scripts.verificar_azure` (ver `docs/azure-setup.md`).

Si en el futuro se agrega una implementación nueva (S3, GCS), los mismos
tests deberían pasar contra ella — ése es el propósito del contrato.
"""

from __future__ import annotations

import pytest

from pokegrading.compartido.almacenamiento import (
    AlmacenamientoEnMemoria,
    IAlmacenamientoImagenes,
)


@pytest.fixture
def almacenamiento() -> IAlmacenamientoImagenes:
    """Cada test recibe una instancia fresca para evitar contaminación."""
    return AlmacenamientoEnMemoria()


@pytest.mark.asyncio
async def test_implementa_protocolo(
    almacenamiento: IAlmacenamientoImagenes,
) -> None:
    """EnMemoria debe satisfacer el Protocol en runtime."""
    assert isinstance(almacenamiento, IAlmacenamientoImagenes)


@pytest.mark.asyncio
async def test_guardar_devuelve_url_no_vacia(
    almacenamiento: IAlmacenamientoImagenes,
) -> None:
    url = await almacenamiento.guardar(
        "cartas", "test/frente.jpg", b"datos", "image/jpeg"
    )
    assert url
    assert isinstance(url, str)


@pytest.mark.asyncio
async def test_obtener_url_devuelve_misma_url_que_guardar(
    almacenamiento: IAlmacenamientoImagenes,
) -> None:
    url_guardar = await almacenamiento.guardar(
        "cartas", "k.jpg", b"v", "image/jpeg"
    )
    url_obtener = await almacenamiento.obtener_url("cartas", "k.jpg")
    assert url_guardar == url_obtener


@pytest.mark.asyncio
async def test_existe_true_tras_guardar(
    almacenamiento: IAlmacenamientoImagenes,
) -> None:
    await almacenamiento.guardar("cartas", "x/y.jpg", b"data", "image/jpeg")
    assert await almacenamiento.existe("cartas", "x/y.jpg")


@pytest.mark.asyncio
async def test_existe_false_si_clave_no_existe(
    almacenamiento: IAlmacenamientoImagenes,
) -> None:
    assert not await almacenamiento.existe("cartas", "no/existe.jpg")


@pytest.mark.asyncio
async def test_sobrescribir_misma_clave(
    almacenamiento: IAlmacenamientoImagenes,
) -> None:
    """Guardar 2 veces con la misma clave sobrescribe (semantica idempotente)."""
    await almacenamiento.guardar("cartas", "k.jpg", b"v1", "image/jpeg")
    await almacenamiento.guardar("cartas", "k.jpg", b"v2", "image/jpeg")

    # La verificación específica del contenido es propia del fake
    assert isinstance(almacenamiento, AlmacenamientoEnMemoria)
    assert almacenamiento.leer_contenido("cartas", "k.jpg") == b"v2"


@pytest.mark.asyncio
async def test_eliminar_recurso_existente(
    almacenamiento: IAlmacenamientoImagenes,
) -> None:
    await almacenamiento.guardar("cartas", "del.jpg", b"data", "image/jpeg")
    await almacenamiento.eliminar("cartas", "del.jpg")
    assert not await almacenamiento.existe("cartas", "del.jpg")


@pytest.mark.asyncio
async def test_eliminar_inexistente_es_idempotente(
    almacenamiento: IAlmacenamientoImagenes,
) -> None:
    """Eliminar algo que no existe NO debe lanzar excepción."""
    await almacenamiento.eliminar("cartas", "no/existe.jpg")


@pytest.mark.asyncio
async def test_aislamiento_entre_contenedores(
    almacenamiento: IAlmacenamientoImagenes,
) -> None:
    """Misma clave en contenedores distintos = recursos distintos."""
    await almacenamiento.guardar("c1", "k.jpg", b"v1", "image/jpeg")

    assert await almacenamiento.existe("c1", "k.jpg")
    assert not await almacenamiento.existe("c2", "k.jpg")


@pytest.mark.asyncio
async def test_content_type_se_preserva(
    almacenamiento: IAlmacenamientoImagenes,
) -> None:
    """Verificación específica de la implementación EnMemoria."""
    assert isinstance(almacenamiento, AlmacenamientoEnMemoria)
    await almacenamiento.guardar("cartas", "k.png", b"v", "image/png")
    assert almacenamiento.leer_content_type("cartas", "k.png") == "image/png"
