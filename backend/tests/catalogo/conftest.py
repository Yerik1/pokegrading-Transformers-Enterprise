"""Fixtures específicos del módulo `catalogo`.

Las imágenes se generan en memoria con Pillow — no hay archivos binarios
en el repo. Las fixtures cubren los casos comunes (válida, muy chica,
muy grande, corrupta, HEIC-fake) que usan los tests de validación.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image


def _crear_imagen_pillow(formato: str, size: tuple[int, int]) -> bytes:
    """Genera una imagen sólida del color rojo en el formato pedido."""
    img = Image.new("RGB", size, color=(220, 50, 50))
    buf = io.BytesIO()
    img.save(buf, format=formato)
    return buf.getvalue()


@pytest.fixture
def imagen_jpeg_valida() -> bytes:
    """800×1120 JPEG (cumple resolución mínima 600×840)."""
    return _crear_imagen_pillow("JPEG", (800, 1120))


@pytest.fixture
def imagen_png_valida() -> bytes:
    return _crear_imagen_pillow("PNG", (800, 1120))


@pytest.fixture
def imagen_pequena() -> bytes:
    """200×200: bajo la resolución mínima."""
    return _crear_imagen_pillow("JPEG", (200, 200))


@pytest.fixture
def imagen_enorme() -> bytes:
    """4500×6500: sobre la resolución máxima."""
    return _crear_imagen_pillow("JPEG", (4500, 6500))


@pytest.fixture
def imagen_corrupta() -> bytes:
    """Bytes con magic JPEG pero contenido inválido (no decodificable)."""
    return b"\xff\xd8\xff\xe0" + b"X" * 500


@pytest.fixture
def archivo_heic_falso() -> bytes:
    """Bytes que aparecen como HEIC por magic bytes ISO ftyp.

    Formato: length(4) + 'ftyp' + brand + ...
    """
    return b"\x00\x00\x00\x20ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 100


@pytest.fixture
def archivo_no_imagen() -> bytes:
    """Texto plano (no es una imagen)."""
    return b"esto no es una imagen, es texto plano"
