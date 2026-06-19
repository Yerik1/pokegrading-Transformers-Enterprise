"""Reglas de validación de calidad de imagen para evaluaciones (IQS).

El Image Quality Score evalúa cuatro dimensiones:
1. Resolución suficiente
2. Foco (blur detection via varianza del Laplaciano)
3. Iluminación (brillo promedio)
4. Encuadre (la carta ocupa suficiente área)

Umbral mínimo configurable, default 0.6.
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image, ImageFilter

from pokegrading.compartido.errores import ErrorValidacion

# ---------------------------------------------------------------------------
# Umbrales de validación
# ---------------------------------------------------------------------------

UMBRAL_IQS_DEFAULT: float = 0.6
UMBRAL_BLUR: float = 100.0
BRILLO_MINIMO: float = 40.0
BRILLO_MAXIMO: float = 220.0
RESOLUCION_MINIMA_EVAL: int = 400

# ---------------------------------------------------------------------------
# Constantes de normalización del score compuesto
# Nombradas explícitamente para que su significado sea claro sin contexto.
# ---------------------------------------------------------------------------

# Varianza del Laplaciano a partir de la cual la imagen se considera
# perfectamente nítida (score_blur = 1.0). Valores mayores no suman más.
DIVISOR_NORMALIZACION_BLUR: float = 1000.0

# Brillo neutro ideal (punto medio de 0-255). El score de brillo es máximo
# cuando el brillo promedio de la imagen se acerca a este valor.
BRILLO_NEUTRO: float = 128.0

# Resolución de referencia considerada "ideal" para evaluación de grading.
# Se usa para normalizar el score de resolución entre 0.0 y 1.0.
RESOLUCION_REFERENCIA_ANCHO: int = 800
RESOLUCION_REFERENCIA_ALTO: int = 1120

# Pesos del score compuesto — deben sumar 1.0
PESO_BLUR: float = 0.4
PESO_BRILLO: float = 0.3
PESO_RESOLUCION: float = 0.3


# ---------------------------------------------------------------------------
# Funciones de score por dimensión (importables de forma independiente)
# ---------------------------------------------------------------------------


def calcular_score_blur(img_gris: Image.Image) -> float:
    """Calcula el score de nitidez usando la varianza del Laplaciano.

    Args:
        img_gris: imagen en escala de grises (modo L).

    Returns:
        Score entre 0.0 y 1.0. Valores cercanos a 1.0 indican buena nitidez.
    """
    laplaciano = np.array(img_gris.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    varianza = float(np.var(laplaciano))
    return min(varianza / DIVISOR_NORMALIZACION_BLUR, 1.0)


def calcular_score_brillo(arr: np.ndarray) -> float:
    """Calcula el score de iluminación basado en el brillo promedio.

    Args:
        arr: array numpy de la imagen en escala de grises (float32).

    Returns:
        Score entre 0.0 y 1.0. Máximo cuando el brillo se acerca a BRILLO_NEUTRO.
    """
    brillo = float(np.mean(arr))
    return 1.0 - abs(brillo - BRILLO_NEUTRO) / BRILLO_NEUTRO


def calcular_score_resolucion(ancho: int, alto: int) -> float:
    """Calcula el score de resolución relativo a la resolución de referencia.

    Args:
        ancho: ancho de la imagen en píxeles.
        alto: alto de la imagen en píxeles.

    Returns:
        Score entre 0.0 y 1.0. Llega a 1.0 al alcanzar la resolución de referencia.
    """
    referencia = RESOLUCION_REFERENCIA_ANCHO * RESOLUCION_REFERENCIA_ALTO
    return min((ancho * alto) / referencia, 1.0)


# ---------------------------------------------------------------------------
# Validaciones por dimensión (lanzan ErrorValidacion si el criterio falla)
# ---------------------------------------------------------------------------


def _validar_resolucion(ancho: int, alto: int, campo: str) -> None:
    if ancho < RESOLUCION_MINIMA_EVAL or alto < RESOLUCION_MINIMA_EVAL:
        raise ErrorValidacion(
            codigo="iq_resolucion_insuficiente",
            mensaje=(
                f"La imagen tiene resolución insuficiente ({ancho}x{alto}px). "
                f"Mínimo requerido: {RESOLUCION_MINIMA_EVAL}px en cada lado."
            ),
            campo=campo,
        )


def _validar_blur(varianza_laplaciano: float, campo: str) -> None:
    """Valida nitidez a partir de una varianza ya calculada.

    Recibe el valor pre-calculado (en vez de recalcularlo a partir de
    la imagen) para no repetir el filtro de bordes dos veces sobre la
    misma imagen: el score y la validación comparten un único cálculo.
    """
    if varianza_laplaciano < UMBRAL_BLUR:
        raise ErrorValidacion(
            codigo="iq_imagen_borrosa",
            mensaje=(
                "La imagen está borrosa. "
                "Asegurate de que la carta esté bien enfocada antes de capturar."
            ),
            campo=campo,
        )


def _validar_brillo(brillo_promedio: float, campo: str) -> None:
    """Valida iluminación a partir de un brillo ya calculado.

    Recibe el valor pre-calculado por la misma razón que `_validar_blur`:
    evitar recorrer el array de píxeles dos veces.
    """
    if brillo_promedio < BRILLO_MINIMO:
        raise ErrorValidacion(
            codigo="iq_iluminacion_insuficiente",
            mensaje=(
                "La imagen tiene poca iluminación. "
                "Capturá la carta en un ambiente con mejor luz."
            ),
            campo=campo,
        )
    if brillo_promedio > BRILLO_MAXIMO:
        raise ErrorValidacion(
            codigo="iq_sobreexposicion",
            mensaje=(
                "La imagen está sobreexpuesta. "
                "Evitá la luz directa sobre la carta al capturar."
            ),
            campo=campo,
        )


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def calcular_iq_score(imagen_bytes: bytes, campo: str) -> float:
    """Calcula el Image Quality Score de una imagen.

    Args:
        imagen_bytes: bytes crudos de la imagen.
        campo: nombre del campo para mensajes de error.

    Returns:
        Score entre 0.0 y 1.0.

    Raises:
        ErrorValidacion: si la imagen falla alguna dimensión crítica.
    """
    img = Image.open(BytesIO(imagen_bytes)).convert("RGB")
    ancho, alto = img.size

    _validar_resolucion(ancho, alto, campo)

    img_gris = img.convert("L")
    arr = np.array(img_gris, dtype=np.float32)

    # Cada dimensión se calcula una sola vez en su forma cruda (sin
    # normalizar a 0-1), y ese mismo valor crudo se usa tanto para
    # validar el umbral mínimo como para derivar el score normalizado.
    # Importante: la varianza/brillo se calculan ANTES de aplicar
    # min()/normalización, para no perder precisión cuando el valor
    # real supera el divisor de normalización.
    laplaciano = np.array(img_gris.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    varianza_laplaciano = float(np.var(laplaciano))
    brillo_promedio = float(np.mean(arr))

    _validar_blur(varianza_laplaciano, campo)
    _validar_brillo(brillo_promedio, campo)

    score_blur = min(varianza_laplaciano / DIVISOR_NORMALIZACION_BLUR, 1.0)
    score_brillo = 1.0 - abs(brillo_promedio - BRILLO_NEUTRO) / BRILLO_NEUTRO
    score_resolucion = calcular_score_resolucion(ancho, alto)

    score = round(
        score_blur * PESO_BLUR
        + score_brillo * PESO_BRILLO
        + score_resolucion * PESO_RESOLUCION,
        4,
    )

    return score