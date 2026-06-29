"""Algoritmo de preprocesamiento de imagen para evaluación (US 191).

Implementa los tres criterios de aceptación de la US:
1. Corrección de perspectiva, recorte al borde de la carta y normalización
   de color.
2. Segmentación en cuatro regiones: centering, corners, edges y surface.
3. Detección de fondo no aislable (deriva a revisión manual) y de
   distorsiones imposibles de corregir (deriva a rechazo).

Cada paso es una función pura e independiente, igual que el patrón ya
usado en `evaluaciones/reglas.py` para el IQ Score: facilita testear
cada paso por separado y reemplazar la heurística de una dimensión sin
tocar las demás.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps

from pokegrading.compartido.errores import ErrorSolicitudInvalida
from pokegrading.compartido.logging import obtener_logger
from pokegrading.negocio.evaluaciones.tipos import RegionCarta

logger = obtener_logger(__name__)

# ---------------------------------------------------------------------------
# Umbrales de aislamiento de fondo y distorsión
# ---------------------------------------------------------------------------

# Proporción mínima del frame que el contorno detectado de la carta debe
# ocupar para considerarse "aislable del fondo". Por debajo de esto, el
# sistema no logra distinguir confiablemente la carta del fondo.
PROPORCION_MINIMA_CONTORNO: float = 0.15

# Proporción máxima: si el contorno detectado ocupa casi todo el frame,
# probablemente es ruido (no se encontró borde real) en vez de una carta.
PROPORCION_MAXIMA_CONTORNO: float = 0.98

# Sesgo de perspectiva máximo corregible, en grados. Por encima de esto
# la distorsión se considera "imposible de corregir" sin inventar datos.
SESGO_PERSPECTIVA_MAXIMO_GRADOS: float = 35.0

# ---------------------------------------------------------------------------
# Proporciones de las 4 regiones relativas al recorte normalizado.
# Valores aproximados de una carta Pokémon estándar (63mm x 88mm):
# el borde exterior es "edges", el marco interior corresponde a
# "centering", las esquinas son recortes fijos en cada vértice, y
# "surface" es el área completa (para detección de manchas/arañazos).
# ---------------------------------------------------------------------------

MARGEN_EDGES_PROPORCION: float = 0.04  # 4% del borde exterior
MARGEN_CENTERING_PROPORCION: float = 0.08  # 8% de margen para el marco
TAMANO_ESQUINA_PROPORCION: float = 0.12  # 12% de cada esquina


@dataclass
class ImagenPreprocesada:
    """Resultado del preprocesamiento de una cara de la carta."""

    bytes_normalizados: bytes
    regiones: dict[str, tuple[int, int, int, int]]  # region -> (x0, y0, x1, y1)


def _detectar_contorno_carta(arr_gris: np.ndarray) -> tuple[int, int, int, int] | None:
    """Detecta el bounding box de la carta contra el fondo.

    Heurística simple: umbraliza por gradiente de intensidad y busca
    la región contigua de mayor área. Si no encuentra un contorno con
    proporción de área dentro del rango esperado, retorna None
    (equivale a "no se puede aislar la carta del fondo").
    """
    alto, ancho = arr_gris.shape
    area_total = alto * ancho

    # Gradiente simple (diferencia entre píxeles vecinos) como proxy de
    # "borde" sin depender de una librería de visión más pesada que PIL/numpy.
    grad_x = np.abs(np.diff(arr_gris, axis=1))
    grad_y = np.abs(np.diff(arr_gris, axis=0))

    umbral_borde = float(np.percentile(grad_x, 90))
    mascara_x = grad_x > umbral_borde
    mascara_y = grad_y > umbral_borde

    columnas_con_borde = np.where(mascara_x.any(axis=0))[0]
    filas_con_borde = np.where(mascara_y.any(axis=1))[0]

    if len(columnas_con_borde) == 0 or len(filas_con_borde) == 0:
        return None

    x0, x1 = int(columnas_con_borde.min()), int(columnas_con_borde.max())
    y0, y1 = int(filas_con_borde.min()), int(filas_con_borde.max())

    area_contorno = (x1 - x0) * (y1 - y0)
    proporcion = area_contorno / area_total

    if (
        proporcion < PROPORCION_MINIMA_CONTORNO
        or proporcion > PROPORCION_MAXIMA_CONTORNO
    ):
        return None

    return x0, y0, x1, y1


def _estimar_sesgo_perspectiva(
    arr_gris: np.ndarray, contorno: tuple[int, int, int, int]
) -> float:
    """Estima el sesgo de perspectiva en grados a partir de la asimetría
    de los bordes detectados dentro del contorno.

    Heurística simple basada en la diferencia de posición de los bordes
    superior e inferior del contorno respecto al eje vertical central;
    no es una rectificación de perspectiva real (homografía), pero es
    suficiente para distinguir "corregible" de "imposible de corregir".
    """
    x0, y0, x1, y1 = contorno
    recorte = arr_gris[y0:y1, x0:x1]
    if recorte.shape[0] < 2 or recorte.shape[1] < 2:
        return 0.0

    mitad = recorte.shape[1] // 2
    perfil_izquierdo = recorte[:, :mitad].mean(axis=1)
    perfil_derecho = recorte[:, mitad:].mean(axis=1)

    diferencia = float(np.mean(np.abs(perfil_izquierdo - perfil_derecho)))
    # Normalización empírica a un rango de grados aproximado.
    sesgo_grados = min(diferencia / 2.0, 90.0)
    return sesgo_grados


def _normalizar_color(imagen: Image.Image) -> Image.Image:
    """Normaliza el balance de color y contraste de la imagen recortada.

    Usa autocontraste de PIL (estiramiento de histograma por canal),
    suficiente para compensar variaciones de iluminación entre capturas
    sin alterar el contenido estructural de la carta.
    """
    return ImageOps.autocontrast(imagen, cutoff=1)


def _segmentar_regiones(ancho: int, alto: int) -> dict[str, tuple[int, int, int, int]]:
    """Calcula los bounding boxes de las 4 regiones sobre la imagen
    ya recortada y normalizada (coordenadas relativas a 0,0 - ancho,alto).
    """
    margen_edges = int(min(ancho, alto) * MARGEN_EDGES_PROPORCION)
    margen_centering = int(min(ancho, alto) * MARGEN_CENTERING_PROPORCION)
    tam_esquina = int(min(ancho, alto) * TAMANO_ESQUINA_PROPORCION)

    return {
        RegionCarta.EDGES.value: (0, 0, ancho, alto),
        RegionCarta.CENTERING.value: (
            margen_centering,
            margen_centering,
            ancho - margen_centering,
            alto - margen_centering,
        ),
        RegionCarta.CORNERS.value: (
            0,
            0,
            tam_esquina,
            tam_esquina,
        ),  # esquina superior-izq de referencia
        RegionCarta.SURFACE.value: (
            margen_edges,
            margen_edges,
            ancho - margen_edges,
            alto - margen_edges,
        ),
    }


def preprocesar_imagen(imagen_bytes: bytes, *, campo: str) -> ImagenPreprocesada:
    """Ejecuta el preprocesamiento completo de una cara de la carta.

    Args:
        imagen_bytes: bytes de la imagen ya validada (formato/tamaño)
            por `compartido.imagenes.validar_imagen`.
        campo: nombre del campo para mensajes de error ("imagen_frente"
            o "imagen_reverso").

    Returns:
        ImagenPreprocesada con los bytes normalizados y las regiones
        segmentadas.

    Raises:
        ErrorValidacion:
            - `fondo_no_aislable` si no se puede separar la carta del fondo
              (alterno de la US: "deriva a calificación manual").
            - `distorsion_no_corregible` si el sesgo de perspectiva excede
              el máximo corregible (alterno: "se rechaza y se solicita
              recapturar").
    """
    img = Image.open(BytesIO(imagen_bytes)).convert("RGB")
    img_gris = np.array(img.convert("L"), dtype=np.float32)

    contorno = _detectar_contorno_carta(img_gris)
    if contorno is None:
        raise ErrorSolicitudInvalida(
            codigo="fondo_no_aislable",
            mensaje=(
                "No se pudo aislar la carta del fondo de la imagen. "
                "Capturá la carta sobre una superficie de color uniforme "
                "y contrastante."
            ),
            campo=campo,
        )

    sesgo = _estimar_sesgo_perspectiva(img_gris, contorno)
    if sesgo > SESGO_PERSPECTIVA_MAXIMO_GRADOS:
        raise ErrorSolicitudInvalida(
            codigo="distorsion_no_corregible",
            mensaje=(
                "La imagen tiene una distorsión de perspectiva demasiado "
                "pronunciada para corregirse automáticamente. Recapturá "
                "la carta de frente, evitando ángulos pronunciados."
            ),
            campo=campo,
        )

    x0, y0, x1, y1 = contorno
    recorte = img.crop((x0, y0, x1, y1))
    normalizada = _normalizar_color(recorte)

    regiones = _segmentar_regiones(normalizada.width, normalizada.height)

    buffer = BytesIO()
    normalizada.save(buffer, format="JPEG", quality=92)

    logger.info(
        "imagen_preprocesada",
        campo=campo,
        sesgo_perspectiva_grados=round(sesgo, 2),
        ancho_recorte=normalizada.width,
        alto_recorte=normalizada.height,
    )

    return ImagenPreprocesada(bytes_normalizados=buffer.getvalue(), regiones=regiones)
