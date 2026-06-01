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

UMBRAL_IQS_DEFAULT: float = 0.6
UMBRAL_BLUR: float = 100.0
BRILLO_MINIMO: float = 40.0
BRILLO_MAXIMO: float = 220.0
RESOLUCION_MINIMA_EVAL: int = 400


def calcular_iq_score(imagen_bytes: bytes, campo: str) -> float:
    """Calcula el Image Quality Score de una imagen.

    Args:
        imagen_bytes: bytes crudos de la imagen.
        campo: nombre del campo para mensajes de error.

    Returns:
        Score entre 0.0 y 1.0.

    Raises:
        ErrorValidacion: si la imagen falla alguna dimensión crítica
            con descripción de la causa.
    """
    img = Image.open(BytesIO(imagen_bytes)).convert("RGB")
    ancho, alto = img.size

    # 1. Resolución
    if ancho < RESOLUCION_MINIMA_EVAL or alto < RESOLUCION_MINIMA_EVAL:
        raise ErrorValidacion(
            codigo="iq_resolucion_insuficiente",
            mensaje=(
                f"La imagen tiene resolución insuficiente ({ancho}x{alto}px). "
                f"Mínimo requerido: {RESOLUCION_MINIMA_EVAL}px en cada lado."
            ),
            campo=campo,
        )

    # 2. Foco — varianza del Laplaciano
    img_gris = img.convert("L")
    arr = np.array(img_gris, dtype=np.float32)
    laplaciano = np.array(img_gris.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    varianza_blur = float(np.var(laplaciano))

    if varianza_blur < UMBRAL_BLUR:
        raise ErrorValidacion(
            codigo="iq_imagen_borrosa",
            mensaje=(
                "La imagen está borrosa. "
                "Asegurate de que la carta esté bien enfocada antes de capturar."
            ),
            campo=campo,
        )

    # 3. Iluminación — brillo promedio
    brillo = float(np.mean(arr))
    if brillo < BRILLO_MINIMO:
        raise ErrorValidacion(
            codigo="iq_iluminacion_insuficiente",
            mensaje=(
                "La imagen tiene poca iluminación. "
                "Capturá la carta en un ambiente con mejor luz."
            ),
            campo=campo,
        )
    if brillo > BRILLO_MAXIMO:
        raise ErrorValidacion(
            codigo="iq_sobreexposicion",
            mensaje=(
                "La imagen está sobreexpuesta. "
                "Evitá la luz directa sobre la carta al capturar."
            ),
            campo=campo,
        )

    # 4. Score compuesto normalizado
    score_blur = min(varianza_blur / 1000.0, 1.0)
    score_brillo = 1.0 - abs(brillo - 128.0) / 128.0
    score_resolucion = min((ancho * alto) / (800 * 1120), 1.0)
    score = round((score_blur * 0.4 + score_brillo * 0.3 + score_resolucion * 0.3), 4)

    return score
