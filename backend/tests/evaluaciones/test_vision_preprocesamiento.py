"""Tests del algoritmo de preprocesamiento de carta (US 191).

Verifica las funciones puras de vision_preprocesamiento.py:
- _segmentar_regiones: proporciones y claves correctas
- preprocesar_imagen: casos de error y caso feliz
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from pokegrading.compartido.errores import ErrorSolicitudInvalida
from pokegrading.negocio.evaluaciones.algoritmo.vision_preprocesamiento import (
    ImagenPreprocesada,
    _segmentar_regiones,
    preprocesar_imagen,
)

# ---------------------------------------------------------------------------
# Helpers para generar imágenes sintéticas
# ---------------------------------------------------------------------------


def _imagen_bytes(ancho: int = 800, alto: int = 1100, modo: str = "RGB") -> bytes:
    """Imagen JPG sintética del tamaño dado."""
    img = Image.new(modo, (ancho, alto), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _imagen_con_carta(
    ancho: int = 800,
    alto: int = 1100,
    margen: int = 80,
    color_fondo: tuple = (255, 255, 255),
    color_carta: tuple = (50, 50, 50),
) -> bytes:
    """Imagen con un rectángulo oscuro sobre fondo claro — simula carta con contraste."""
    img = Image.new("RGB", (ancho, alto), color=color_fondo)
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [margen, margen, ancho - margen, alto - margen],
        fill=color_carta,
        outline=(0, 0, 0),
        width=10,
    )
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# _segmentar_regiones
# ---------------------------------------------------------------------------


def test_segmentar_regiones_devuelve_4_regiones() -> None:
    regiones = _segmentar_regiones(800, 1100)
    assert len(regiones) == 4


def test_segmentar_regiones_tiene_claves_correctas() -> None:
    regiones = _segmentar_regiones(800, 1100)
    assert "centering" in regiones
    assert "corners" in regiones
    assert "edges" in regiones
    assert "surface" in regiones


def test_segmentar_regiones_coordenadas_dentro_de_imagen() -> None:
    ancho, alto = 800, 1100
    regiones = _segmentar_regiones(ancho, alto)
    for nombre, (x1, y1, x2, y2) in regiones.items():
        assert x1 >= 0, f"{nombre}: x1 negativo"
        assert y1 >= 0, f"{nombre}: y1 negativo"
        assert x2 <= ancho, f"{nombre}: x2 fuera del ancho"
        assert y2 <= alto, f"{nombre}: y2 fuera del alto"
        assert x1 < x2, f"{nombre}: x1 >= x2"
        assert y1 < y2, f"{nombre}: y1 >= y2"


def test_segmentar_regiones_todas_tienen_area_positiva() -> None:
    regiones = _segmentar_regiones(800, 1100)
    for nombre, (x1, y1, x2, y2) in regiones.items():
        area = (x2 - x1) * (y2 - y1)
        assert area > 0, f"{nombre} tiene área cero"


# ---------------------------------------------------------------------------
# preprocesar_imagen
# ---------------------------------------------------------------------------


def test_preprocesar_imagen_fondo_uniforme_sin_carta_lanza_error() -> None:
    """Imagen sin carta detectable → ErrorSolicitudInvalida fondo_no_aislable."""
    imagen = _imagen_bytes(800, 1100)
    with pytest.raises(ErrorSolicitudInvalida) as exc:
        preprocesar_imagen(imagen, campo="imagen_frente")
    assert exc.value.codigo == "fondo_no_aislable"


def test_preprocesar_imagen_con_carta_devuelve_imagen_preprocesada() -> None:
    """Carta con buen contraste → ImagenPreprocesada con regiones."""
    imagen = _imagen_con_carta()
    resultado = preprocesar_imagen(imagen, campo="imagen_frente")
    assert isinstance(resultado, ImagenPreprocesada)
    assert isinstance(resultado.bytes_normalizados, bytes)
    assert len(resultado.bytes_normalizados) > 0
    assert isinstance(resultado.regiones, dict)
    assert len(resultado.regiones) == 4


def test_preprocesar_imagen_campo_reverso_funciona() -> None:
    """El campo 'imagen_reverso' también funciona con la misma imagen."""
    imagen = _imagen_con_carta()
    resultado = preprocesar_imagen(imagen, campo="imagen_reverso")
    assert isinstance(resultado, ImagenPreprocesada)


def test_preprocesar_imagen_regiones_tienen_claves_correctas() -> None:
    imagen = _imagen_con_carta()
    resultado = preprocesar_imagen(imagen, campo="imagen_frente")
    assert "centering" in resultado.regiones
    assert "corners" in resultado.regiones
    assert "edges" in resultado.regiones
    assert "surface" in resultado.regiones
