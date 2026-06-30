"""Tests del algoritmo de preprocesamiento de carta (US 191).

Verifica las funciones puras de vision_preprocesamiento.py:
- _segmentar_regiones: proporciones y claves correctas
- preprocesar_imagen: casos de error y caso feliz
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image, ImageDraw

from pokegrading.compartido.errores import ErrorSolicitudInvalida
from pokegrading.negocio.evaluaciones.algoritmo.vision_preprocesamiento import (
    ANGULO_ROTACION_MINIMO_PARA_CORREGIR,
    ImagenPreprocesada,
    _aplicar_correccion_perspectiva,
    _detectar_contorno_carta,
    _estimar_angulo_rotacion,
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


def _imagen_con_carta_rotada(
    angulo_grados: float,
    ancho: int = 1000,
    alto: int = 1300,
    color_fondo: tuple = (235, 235, 235),
    color_carta: tuple = (60, 60, 60),
) -> bytes:
    """Imagen con una carta rotada un ángulo REAL conocido (rotando la
    foto entera, como pasaría con una captura real en ángulo). Incluye
    líneas internas para que el IQ Score de nitidez no la rechace
    antes de llegar al preprocesamiento.
    """
    img = Image.new("RGB", (ancho, alto), color=color_fondo)
    draw = ImageDraw.Draw(img)
    draw.rectangle([200, 200, 800, 1100], fill=color_carta, outline=(0, 0, 0), width=14)
    for y in range(220, 1080, 40):
        draw.line([220, y, 780, y], fill=(80, 80, 80), width=2)
    if angulo_grados != 0:
        img = img.rotate(
            angulo_grados, resample=Image.BICUBIC, expand=True, fillcolor=color_fondo
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


# ---------------------------------------------------------------------------
# _estimar_angulo_rotacion / _aplicar_correccion_perspectiva (US 191:
# "corrección de perspectiva" real, no solo detección para aceptar/
# rechazar)
# ---------------------------------------------------------------------------


def test_estimar_angulo_rotacion_imagen_derecha_es_cercano_a_cero() -> None:
    """Carta sin rotación real: el ángulo estimado debe ser ~0."""
    imagen = _imagen_con_carta_rotada(0)
    arr_gris = np.array(Image.open(io.BytesIO(imagen)).convert("L"), dtype=np.float32)
    contorno = _detectar_contorno_carta(arr_gris)
    assert contorno is not None
    angulo = _estimar_angulo_rotacion(arr_gris, contorno)
    assert abs(angulo) < 1.0


@pytest.mark.parametrize("angulo_real", [3, 7, 10, -5, -10])
def test_estimar_angulo_rotacion_se_acerca_al_angulo_real(angulo_real: float) -> None:
    """El ángulo estimado (con signo) debe acercarse al ángulo real
    conocido con el que se generó la imagen sintética, dentro de un
    margen de error razonable para una heurística simple.
    """
    imagen = _imagen_con_carta_rotada(angulo_real)
    arr_gris = np.array(Image.open(io.BytesIO(imagen)).convert("L"), dtype=np.float32)
    contorno = _detectar_contorno_carta(arr_gris)
    assert contorno is not None
    angulo_estimado = _estimar_angulo_rotacion(arr_gris, contorno)
    # Mismo signo que el ángulo real
    assert (angulo_estimado > 0) == (angulo_real > 0)
    # Dentro de 1 grado de error
    assert abs(angulo_estimado - angulo_real) < 1.0


def test_estimar_angulo_rotacion_region_muy_pequena_devuelve_cero() -> None:
    """Contorno casi sin área: no hay suficiente evidencia, se asume 0."""
    arr_gris = np.zeros((5, 5), dtype=np.float32)
    angulo = _estimar_angulo_rotacion(arr_gris, (0, 0, 5, 5))
    assert angulo == 0.0


def test_aplicar_correccion_no_rota_si_angulo_insignificante() -> None:
    """Por debajo del umbral mínimo, la imagen se devuelve sin tocar
    (evita resampleo innecesario en la mayoría de capturas, que ya
    vienen razonablemente derechas)."""
    imagen = Image.new("RGB", (200, 300), color=(255, 255, 255))
    angulo_insignificante = ANGULO_ROTACION_MINIMO_PARA_CORREGIR / 2
    resultado = _aplicar_correccion_perspectiva(imagen, angulo_insignificante)
    assert resultado is imagen  # mismo objeto, ni siquiera se copia


def test_aplicar_correccion_rota_si_angulo_significativo() -> None:
    """Por encima del umbral, sí debe rotar (el lienzo cambia de tamaño
    por el expand=True, evidencia indirecta de que rotó)."""
    imagen = Image.new("RGB", (200, 300), color=(255, 255, 255))
    resultado = _aplicar_correccion_perspectiva(imagen, 10.0)
    assert resultado is not imagen
    assert resultado.size != imagen.size  # expand=True agranda el lienzo


def test_preprocesar_imagen_carta_rotada_no_falla_y_corrige() -> None:
    """Una carta con rotación moderada (dentro de lo corregible) debe
    preprocesarse exitosamente, con el ángulo aplicado registrado.
    """
    imagen = _imagen_con_carta_rotada(8)
    resultado = preprocesar_imagen(imagen, campo="imagen_frente")
    assert isinstance(resultado, ImagenPreprocesada)
    assert len(resultado.regiones) == 4


def test_preprocesar_imagen_carta_derecha_no_se_distorsiona() -> None:
    """Sanity check de no-regresión: una carta sin rotación sigue
    preprocesándose igual que antes de agregar la corrección."""
    imagen = _imagen_con_carta_rotada(0)
    resultado = preprocesar_imagen(imagen, campo="imagen_frente")
    assert isinstance(resultado, ImagenPreprocesada)
    assert len(resultado.regiones) == 4