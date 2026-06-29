"""Algoritmo de calificación de carta (US 193).

Calcula los 4 subgrades (centering, corners, edges, surface) en escala
1.0-10.0 a partir de las regiones segmentadas por el preprocesamiento
(US 191), los compara contra un baseline calibrado, y deriva un grado
final coherente con banda de incertidumbre.

Cada dimensión se calcula con una heurística de visión por computadora
simple, reutilizando el mismo enfoque de varianza del Laplaciano ya
usado en `evaluaciones/reglas.py` para el IQ Score:

- centering: simetría del margen entre el borde de la región
  `centering` y el borde exterior de la carta.
- corners: nitidez (varianza del Laplaciano) en las 4 esquinas — una
  esquina doblada o gastada reduce el detalle de alta frecuencia ahí.
- edges: continuidad del contorno detectado en la región `edges` —
  un borde desgastado o con muescas rompe la continuidad de línea recta.
- surface: detección de manchas/arañazos vía varianza local de
  intensidad sobre la región `surface`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

from pokegrading.compartido.logging import obtener_logger
from pokegrading.negocio.evaluaciones.tipos import RegionCarta

logger = obtener_logger(__name__)

# ---------------------------------------------------------------------------
# Escala pública de subgrades y grado final
# ---------------------------------------------------------------------------

SUBGRADE_MINIMO: float = 1.0
SUBGRADE_MAXIMO: float = 10.0

# ---------------------------------------------------------------------------
# Umbrales y constantes de cada heurística (nombradas explícitamente,
# sin números mágicos inline, mismo criterio que evaluaciones/reglas.py)
# ---------------------------------------------------------------------------

# Centering: diferencia de margen máxima tolerada (proporción del ancho
# de región) antes de penalizar el subgrade al mínimo.
DIFERENCIA_MARGEN_MAXIMA: float = 0.30

# Corners/Edges: varianza del Laplaciano de referencia para nitidez
# perfecta (score = 1.0). Mismo concepto que DIVISOR_NORMALIZACION_BLUR
# del IQ Score, pero calibrado para el tamaño típico de una esquina.
DIVISOR_NORMALIZACION_NITIDEZ: float = 800.0

# Surface: desviación estándar local máxima tolerada antes de
# considerarse una mancha/arañazo significativo.
DESVIACION_LOCAL_MAXIMA: float = 25.0

# ---------------------------------------------------------------------------
# Regla de coherencia (US 193, criterio de aceptación explícito):
# "el grado final no excede el subgrade más bajo + 0.5"
# ---------------------------------------------------------------------------

MARGEN_COHERENCIA_GRADO_FINAL: float = 0.5

# Tamaño de muestra mínimo para confiar en un baseline específico de
# (set, acabado) en vez de usar el baseline global como fallback.
MUESTRA_MINIMA_GROUND_TRUTH: int = 30

# Banda de incertidumbre base, ajustada según cuántas dimensiones
# pudieron calcularse con baseline específico vs. global.
BANDA_INCERTIDUMBRE_CON_BASELINE_ESPECIFICO: float = 0.3
BANDA_INCERTIDUMBRE_CON_BASELINE_GLOBAL: float = 0.6


@dataclass
class ReferenciaBaseline:
    """Vista de un `GradingBaseline` desacoplada del modelo ORM, para
    que las funciones puras de este módulo no dependan de SQLAlchemy.
    """

    id: str
    referencia_centering: float
    referencia_corners: float
    referencia_edges: float
    referencia_surface: float
    tamano_muestra: int
    version_algoritmo: str
    es_global: bool


@dataclass
class ResultadoCalificacion:
    """Resultado completo de calcular_calificacion()."""

    subgrade_centering: float | None
    subgrade_corners: float | None
    subgrade_edges: float | None
    subgrade_surface: float | None
    grado_estimado: float | None
    banda_incertidumbre: float | None
    dimension_no_calculable: str | None  # nombre de la dimensión que falló, si alguna


def _score_centering(region_centering: np.ndarray) -> float:
    """Simetría del margen: compara la mitad izquierda vs. derecha y
    superior vs. inferior de la región centering.
    """
    alto, ancho = region_centering.shape
    mitad_h = ancho // 2
    mitad_v = alto // 2

    diff_horizontal = float(
        np.mean(
            np.abs(
                region_centering[:, :mitad_h].mean()
                - region_centering[:, mitad_h:].mean()
            )
        )
    )
    diff_vertical = float(
        np.mean(
            np.abs(
                region_centering[:mitad_v, :].mean()
                - region_centering[mitad_v:, :].mean()
            )
        )
    )
    diferencia_normalizada = (diff_horizontal + diff_vertical) / 2.0 / 255.0

    score = 1.0 - min(diferencia_normalizada / DIFERENCIA_MARGEN_MAXIMA, 1.0)
    return max(score, 0.0)


def _score_nitidez(region: np.ndarray) -> float:
    """Nitidez vía varianza del Laplaciano, reutilizado para corners y edges."""
    img_region = Image.fromarray(region.astype(np.uint8))
    laplaciano = np.array(img_region.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    varianza = float(np.var(laplaciano))
    return min(varianza / DIVISOR_NORMALIZACION_NITIDEZ, 1.0)


def _score_surface(region_surface: np.ndarray) -> float:
    """Detección de manchas/arañazos vía desviación estándar local.

    Una superficie limpia tiene variación de intensidad baja y
    uniforme; manchas o arañazos introducen picos de alta varianza
    local que no corresponden al patrón impreso de la carta.
    """
    desviacion = float(np.std(region_surface))
    score = 1.0 - min(desviacion / DESVIACION_LOCAL_MAXIMA, 1.0)
    return max(score, 0.0)


def _a_escala_publica(score_0_a_1: float) -> float:
    """Proyecta un score interno 0.0-1.0 a la escala pública 1.0-10.0."""
    return round(SUBGRADE_MINIMO + score_0_a_1 * (SUBGRADE_MAXIMO - SUBGRADE_MINIMO), 2)


def calcular_subgrade(
    region_pixeles: np.ndarray, dimension: RegionCarta
) -> float | None:
    """Calcula el subgrade de una dimensión a partir de su región segmentada.

    Returns:
        Subgrade en escala 1.0-10.0, o None si la región no tiene
        suficientes datos para calcularse (ej. recorte vacío).
    """
    if region_pixeles.size == 0 or min(region_pixeles.shape) < 4:
        return None

    if dimension == RegionCarta.CENTERING:
        score = _score_centering(region_pixeles)
    elif dimension in (RegionCarta.CORNERS, RegionCarta.EDGES):
        score = _score_nitidez(region_pixeles)
    elif dimension == RegionCarta.SURFACE:
        score = _score_surface(region_pixeles)
    else:  # pragma: no cover — exhaustivo por el enum
        return None

    return _a_escala_publica(score)


def seleccionar_baseline(
    baseline_especifico: ReferenciaBaseline | None,
    baseline_global: ReferenciaBaseline,
) -> ReferenciaBaseline:
    """Selecciona el baseline a usar, aplicando el fallback de US 193:
    "Selección del baseline calibrado según (set, acabado) cuando hay
    ground truth suficiente; fallback al baseline global registrado
    en el output".
    """
    if (
        baseline_especifico is not None
        and baseline_especifico.tamano_muestra >= MUESTRA_MINIMA_GROUND_TRUTH
    ):
        return baseline_especifico
    return baseline_global


def calcular_grado_final(
    subgrades: dict[str, float | None],
) -> tuple[float | None, float | None]:
    """Deriva el grado final a partir de los subgrades, aplicando la
    regla de coherencia de US 193: "el grado final no excede el
    subgrade más bajo + 0.5".

    Returns:
        (grado_final, subgrade_minimo) — ambos None si ningún subgrade
        pudo calcularse.
    """
    valores = [v for v in subgrades.values() if v is not None]
    if not valores:
        return None, None

    promedio = sum(valores) / len(valores)
    subgrade_minimo = min(valores)
    limite_coherencia = subgrade_minimo + MARGEN_COHERENCIA_GRADO_FINAL

    grado_final = min(promedio, limite_coherencia)
    return round(grado_final, 2), subgrade_minimo


def calcular_banda_incertidumbre(baseline_usado: ReferenciaBaseline) -> float:
    """Calcula la banda de incertidumbre del grado estimado.

    Más estrecha cuando se usó un baseline específico de (set, acabado)
    con suficiente ground truth; más amplia con el baseline global,
    reflejando menor confianza estadística.
    """
    if baseline_usado.es_global:
        return BANDA_INCERTIDUMBRE_CON_BASELINE_GLOBAL
    return BANDA_INCERTIDUMBRE_CON_BASELINE_ESPECIFICO


def calcular_calificacion(
    regiones_por_dimension: dict[str, np.ndarray],
    baseline_especifico: ReferenciaBaseline | None,
    baseline_global: ReferenciaBaseline,
) -> ResultadoCalificacion:
    """Orquesta el cálculo completo de calificación de una carta.

    Args:
        regiones_por_dimension: mapa {dimension: array de píxeles},
            ya recortado por el preprocesamiento (US 191).
        baseline_especifico: baseline de (set, acabado) si existe.
        baseline_global: baseline de fallback, siempre presente.

    Returns:
        ResultadoCalificacion con subgrades, grado final, banda de
        incertidumbre y, si alguna dimensión no pudo calcularse, su
        nombre (para que el servicio decida derivar a revisión manual).
    """
    baseline_usado = seleccionar_baseline(baseline_especifico, baseline_global)

    subgrades: dict[str, float | None] = {}
    dimension_fallida: str | None = None

    for dimension in RegionCarta:
        region = regiones_por_dimension.get(dimension.value)
        if region is None:
            subgrades[dimension.value] = None
            dimension_fallida = dimension.value
            continue
        subgrade = calcular_subgrade(region, dimension)
        subgrades[dimension.value] = subgrade
        if subgrade is None:
            dimension_fallida = dimension.value

    grado_final, subgrade_minimo = calcular_grado_final(subgrades)
    banda = (
        calcular_banda_incertidumbre(baseline_usado)
        if grado_final is not None
        else None
    )

    logger.info(
        "calificacion_calculada",
        subgrades=subgrades,
        grado_estimado=grado_final,
        baseline_es_global=baseline_usado.es_global,
        version_algoritmo=baseline_usado.version_algoritmo,
        dimension_fallida=dimension_fallida,
    )

    return ResultadoCalificacion(
        subgrade_centering=subgrades.get(RegionCarta.CENTERING.value),
        subgrade_corners=subgrades.get(RegionCarta.CORNERS.value),
        subgrade_edges=subgrades.get(RegionCarta.EDGES.value),
        subgrade_surface=subgrades.get(RegionCarta.SURFACE.value),
        grado_estimado=grado_final,
        banda_incertidumbre=banda,
        dimension_no_calculable=dimension_fallida,
    )
