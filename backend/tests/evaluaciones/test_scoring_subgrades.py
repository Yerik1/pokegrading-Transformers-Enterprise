"""Tests del algoritmo de calificación de carta (US 193).

Verifica las funciones puras de scoring_subgrades.py:
- calcular_subgrade por cada dimensión
- seleccionar_baseline con fallback al global
- calcular_grado_final con regla de coherencia
- calcular_banda_incertidumbre
- calcular_calificacion (orquestador)
"""

from __future__ import annotations

import numpy as np

from pokegrading.negocio.evaluaciones.algoritmo.scoring_subgrades import (
    BANDA_INCERTIDUMBRE_CON_BASELINE_ESPECIFICO,
    BANDA_INCERTIDUMBRE_CON_BASELINE_GLOBAL,
    MARGEN_COHERENCIA_GRADO_FINAL,
    MARGEN_MAXIMO_INCOHERENCIA_INTERNA,
    MUESTRA_MINIMA_GROUND_TRUTH,
    ReferenciaBaseline,
    ResultadoCalificacion,
    calcular_banda_incertidumbre,
    calcular_calificacion,
    calcular_grado_final,
    calcular_subgrade,
    detectar_incoherencia_interna,
    seleccionar_baseline,
)
from pokegrading.negocio.evaluaciones.tipos import RegionCarta

# ---------------------------------------------------------------------------
# Fixtures de baseline
# ---------------------------------------------------------------------------


def _baseline_global() -> ReferenciaBaseline:
    return ReferenciaBaseline(
        id="global",
        referencia_centering=0.7,
        referencia_corners=0.7,
        referencia_edges=0.7,
        referencia_surface=0.7,
        tamano_muestra=0,
        version_algoritmo="v1.0",
        es_global=True,
    )


def _baseline_especifico(muestra: int = 50) -> ReferenciaBaseline:
    return ReferenciaBaseline(
        id="especifico",
        referencia_centering=0.8,
        referencia_corners=0.8,
        referencia_edges=0.8,
        referencia_surface=0.8,
        tamano_muestra=muestra,
        version_algoritmo="v1.0",
        es_global=False,
    )


def _region(alto: int = 50, ancho: int = 50, valor: int = 128) -> np.ndarray:
    """Región sintética de tamaño y valor uniformes."""
    return np.full((alto, ancho), valor, dtype=np.uint8)


# ---------------------------------------------------------------------------
# calcular_subgrade
# ---------------------------------------------------------------------------


def test_calcular_subgrade_region_vacia_devuelve_none() -> None:
    region = np.array([], dtype=np.uint8).reshape(0, 0)
    assert calcular_subgrade(region, RegionCarta.CENTERING) is None


def test_calcular_subgrade_region_muy_pequena_devuelve_none() -> None:
    region = np.zeros((2, 2), dtype=np.uint8)
    assert calcular_subgrade(region, RegionCarta.CORNERS) is None


def test_calcular_subgrade_centering_retorna_escala_publica() -> None:
    region = _region(50, 50, 128)
    resultado = calcular_subgrade(region, RegionCarta.CENTERING)
    assert resultado is not None
    assert 1.0 <= resultado <= 10.0


def test_calcular_subgrade_corners_retorna_escala_publica() -> None:
    region = _region(30, 30, 200)
    resultado = calcular_subgrade(region, RegionCarta.CORNERS)
    assert resultado is not None
    assert 1.0 <= resultado <= 10.0


def test_calcular_subgrade_edges_retorna_escala_publica() -> None:
    region = _region(30, 30, 200)
    resultado = calcular_subgrade(region, RegionCarta.EDGES)
    assert resultado is not None
    assert 1.0 <= resultado <= 10.0


def test_calcular_subgrade_surface_retorna_escala_publica() -> None:
    region = _region(50, 50, 100)
    resultado = calcular_subgrade(region, RegionCarta.SURFACE)
    assert resultado is not None
    assert 1.0 <= resultado <= 10.0


def test_calcular_subgrade_centering_perfecto_es_maximo() -> None:
    """Región completamente uniforme → centering perfecto → score 10.0."""
    region = _region(50, 50, 128)
    resultado = calcular_subgrade(region, RegionCarta.CENTERING)
    assert resultado == 10.0


def test_calcular_subgrade_surface_uniforme_es_maximo() -> None:
    """Región sin variación → superficie perfecta → score 10.0."""
    region = _region(50, 50, 128)
    resultado = calcular_subgrade(region, RegionCarta.SURFACE)
    assert resultado == 10.0


def test_calcular_subgrade_surface_con_ruido_es_menor() -> None:
    """Región con alta variación → superficie con arañazos → score menor."""
    rng = np.random.default_rng(42)
    region = rng.integers(0, 255, (50, 50), dtype=np.uint8)
    resultado = calcular_subgrade(region, RegionCarta.SURFACE)
    assert resultado is not None
    assert resultado < 10.0


# ---------------------------------------------------------------------------
# seleccionar_baseline
# ---------------------------------------------------------------------------


def test_seleccionar_baseline_usa_especifico_si_muestra_suficiente() -> None:
    especifico = _baseline_especifico(muestra=MUESTRA_MINIMA_GROUND_TRUTH)
    global_ = _baseline_global()
    resultado = seleccionar_baseline(especifico, global_)
    assert resultado.id == "especifico"


def test_seleccionar_baseline_usa_global_si_muestra_insuficiente() -> None:
    especifico = _baseline_especifico(muestra=MUESTRA_MINIMA_GROUND_TRUTH - 1)
    global_ = _baseline_global()
    resultado = seleccionar_baseline(especifico, global_)
    assert resultado.id == "global"


def test_seleccionar_baseline_usa_global_si_especifico_es_none() -> None:
    global_ = _baseline_global()
    resultado = seleccionar_baseline(None, global_)
    assert resultado.id == "global"


# ---------------------------------------------------------------------------
# calcular_grado_final
# ---------------------------------------------------------------------------


def test_calcular_grado_final_todos_none_devuelve_none() -> None:
    subgrades = {
        "centering": None,
        "corners": None,
        "edges": None,
        "surface": None,
    }
    grado, minimo = calcular_grado_final(subgrades)
    assert grado is None
    assert minimo is None


def test_calcular_grado_final_aplica_regla_coherencia() -> None:
    """Si el promedio excede el mínimo + 0.5, el grado se limita al mínimo + 0.5."""
    subgrades = {
        "centering": 9.0,
        "corners": 9.0,
        "edges": 9.0,
        "surface": 1.0,  # muy bajo → limita el grado
    }
    grado, minimo = calcular_grado_final(subgrades)
    assert minimo == 1.0
    assert grado == round(1.0 + MARGEN_COHERENCIA_GRADO_FINAL, 2)


def test_calcular_grado_final_sin_regla_coherencia_cuando_promedio_bajo() -> None:
    """Si el promedio ya está por debajo del límite, se usa el promedio."""
    subgrades = {
        "centering": 5.0,
        "corners": 5.0,
        "edges": 5.0,
        "surface": 5.0,
    }
    grado, minimo = calcular_grado_final(subgrades)
    assert grado == 5.0
    assert minimo == 5.0


def test_calcular_grado_final_ignora_none_en_subgrades() -> None:
    """Los None se ignoran para el promedio y el mínimo."""
    subgrades = {
        "centering": 8.0,
        "corners": None,
        "edges": 6.0,
        "surface": 7.0,
    }
    grado, minimo = calcular_grado_final(subgrades)
    assert grado is not None
    assert minimo == 6.0


# ---------------------------------------------------------------------------
# detectar_incoherencia_interna
# ---------------------------------------------------------------------------


def test_incoherencia_subgrades_muy_dispares_es_true() -> None:
    """Tres subgrades perfectos y uno pésimo: dispersión extrema."""
    subgrades = {
        "centering": 9.0,
        "corners": 9.0,
        "edges": 9.0,
        "surface": 1.0,
    }
    assert detectar_incoherencia_interna(subgrades) is True


def test_incoherencia_subgrades_homogeneos_es_false() -> None:
    subgrades = {
        "centering": 5.0,
        "corners": 5.0,
        "edges": 5.0,
        "surface": 5.0,
    }
    assert detectar_incoherencia_interna(subgrades) is False


def test_incoherencia_dispersion_moderada_es_false() -> None:
    """Dispersión razonable (no todo es 9,9,9,1) no debe disparar el alterno."""
    subgrades = {
        "centering": 8.0,
        "corners": 7.0,
        "edges": 6.0,
        "surface": 5.0,
    }
    assert detectar_incoherencia_interna(subgrades) is False


def test_incoherencia_con_un_solo_subgrade_es_false() -> None:
    """No hay suficiente información para hablar de dispersión."""
    subgrades = {
        "centering": 7.0,
        "corners": None,
        "edges": None,
        "surface": None,
    }
    assert detectar_incoherencia_interna(subgrades) is False


def test_incoherencia_todos_none_es_false() -> None:
    subgrades = {
        "centering": None,
        "corners": None,
        "edges": None,
        "surface": None,
    }
    assert detectar_incoherencia_interna(subgrades) is False


def test_incoherencia_justo_debajo_del_umbral_es_false() -> None:
    """Dispersión apenas por debajo del umbral no debe disparar el alterno."""
    # diferencia = promedio - (minimo + 0.5). Con surface=7.4 da diferencia ~1.4 (< 1.5).
    subgrades = {"centering": 10.0, "corners": 10.0, "edges": 10.0, "surface": 7.4}
    promedio = sum(subgrades.values()) / 4
    limite = min(subgrades.values()) + MARGEN_COHERENCIA_GRADO_FINAL
    assert (promedio - limite) < MARGEN_MAXIMO_INCOHERENCIA_INTERNA
    assert detectar_incoherencia_interna(subgrades) is False


def test_incoherencia_justo_encima_del_umbral_es_true() -> None:
    """Dispersión apenas por encima del umbral SÍ debe disparar el alterno."""
    # Con surface=7.2 da diferencia ~1.55 (> 1.5).
    subgrades = {"centering": 10.0, "corners": 10.0, "edges": 10.0, "surface": 7.2}
    promedio = sum(subgrades.values()) / 4
    limite = min(subgrades.values()) + MARGEN_COHERENCIA_GRADO_FINAL
    assert (promedio - limite) > MARGEN_MAXIMO_INCOHERENCIA_INTERNA
    assert detectar_incoherencia_interna(subgrades) is True


def test_calcular_calificacion_incoherencia_detectada_propaga_al_resultado() -> None:
    """calcular_calificacion debe exponer incoherencia_detectada en el resultado."""
    regiones = {
        "centering": _region(50, 50, 250),  # va a salir alto (poca asimetria)
        "corners": _region(20, 20, 255),
        "edges": _region(20, 100, 255),
        "surface": _region(
            50, 50, 128
        ),  # uniforme -> alto tambien en este setup sintetico
    }
    resultado = calcular_calificacion(regiones, None, _baseline_global())
    assert hasattr(resultado, "incoherencia_detectada")
    assert isinstance(resultado.incoherencia_detectada, bool)


# ---------------------------------------------------------------------------
# calcular_banda_incertidumbre
# ---------------------------------------------------------------------------


def test_banda_con_baseline_global_es_mayor() -> None:
    global_ = _baseline_global()
    banda = calcular_banda_incertidumbre(global_)
    assert banda == BANDA_INCERTIDUMBRE_CON_BASELINE_GLOBAL


def test_banda_con_baseline_especifico_es_menor() -> None:
    especifico = _baseline_especifico()
    banda = calcular_banda_incertidumbre(especifico)
    assert banda == BANDA_INCERTIDUMBRE_CON_BASELINE_ESPECIFICO


def test_banda_global_mayor_que_especifica() -> None:
    assert (
        BANDA_INCERTIDUMBRE_CON_BASELINE_GLOBAL
        > BANDA_INCERTIDUMBRE_CON_BASELINE_ESPECIFICO
    )


# ---------------------------------------------------------------------------
# calcular_calificacion (orquestador)
# ---------------------------------------------------------------------------


def _regiones_validas() -> dict[str, np.ndarray]:
    return {
        "centering": _region(50, 50, 128),
        "corners": _region(20, 20, 200),
        "edges": _region(20, 100, 200),
        "surface": _region(50, 50, 128),
    }


def test_calcular_calificacion_caso_feliz() -> None:
    resultado = calcular_calificacion(
        _regiones_validas(),
        None,
        _baseline_global(),
    )
    assert isinstance(resultado, ResultadoCalificacion)
    assert resultado.grado_estimado is not None
    assert resultado.banda_incertidumbre == BANDA_INCERTIDUMBRE_CON_BASELINE_GLOBAL
    assert resultado.dimension_no_calculable is None


def test_calcular_calificacion_dimension_faltante_marca_fallida() -> None:
    regiones = _regiones_validas()
    del regiones["surface"]
    resultado = calcular_calificacion(regiones, None, _baseline_global())
    assert resultado.dimension_no_calculable == "surface"
    assert resultado.subgrade_surface is None


def test_calcular_calificacion_usa_baseline_especifico() -> None:
    especifico = _baseline_especifico(muestra=MUESTRA_MINIMA_GROUND_TRUTH)
    resultado = calcular_calificacion(
        _regiones_validas(),
        especifico,
        _baseline_global(),
    )
    assert resultado.banda_incertidumbre == BANDA_INCERTIDUMBRE_CON_BASELINE_ESPECIFICO


def test_calcular_calificacion_persiste_version_del_baseline_realmente_usado() -> None:
    """US 193: 'se persiste con el identificador exacto de versión del
    algoritmo'. Si se usó el baseline específico, version_algoritmo_usada
    y baseline_id_usado deben reflejar el ESPECÍFICO, no el global —
    antes de este fix, el servicio siempre persistía la versión del
    global sin importar cuál se usó de verdad para calificar.
    """
    especifico = _baseline_especifico(muestra=MUESTRA_MINIMA_GROUND_TRUTH)
    especifico.id = "id-del-especifico"
    especifico.version_algoritmo = "v2.0-especifico"
    global_ = _baseline_global()
    global_.id = "id-del-global"
    global_.version_algoritmo = "v1.0-global"

    resultado = calcular_calificacion(_regiones_validas(), especifico, global_)

    assert resultado.version_algoritmo_usada == "v2.0-especifico"
    assert resultado.baseline_id_usado == "id-del-especifico"


def test_calcular_calificacion_sin_especifico_persiste_version_del_global() -> None:
    """Caso fallback: sin baseline específico (o sin muestra suficiente),
    version_algoritmo_usada y baseline_id_usado deben ser los del global.
    """
    global_ = _baseline_global()
    global_.id = "id-del-global"
    global_.version_algoritmo = "v1.0-global"

    resultado = calcular_calificacion(_regiones_validas(), None, global_)

    assert resultado.version_algoritmo_usada == "v1.0-global"
    assert resultado.baseline_id_usado == "id-del-global"


def test_calcular_calificacion_regla_coherencia_verificada() -> None:
    """El grado nunca puede exceder el subgrade mínimo + 0.5."""
    resultado = calcular_calificacion(
        _regiones_validas(),
        None,
        _baseline_global(),
    )
    if resultado.grado_estimado is not None:
        subgrades = [
            resultado.subgrade_centering,
            resultado.subgrade_corners,
            resultado.subgrade_edges,
            resultado.subgrade_surface,
        ]
        minimo = min(s for s in subgrades if s is not None)
        assert (
            resultado.grado_estimado
            <= round(minimo + MARGEN_COHERENCIA_GRADO_FINAL, 2) + 0.01
        )


def test_calcular_calificacion_grado_en_escala_valida() -> None:
    resultado = calcular_calificacion(
        _regiones_validas(),
        None,
        _baseline_global(),
    )
    if resultado.grado_estimado is not None:
        assert 1.0 <= resultado.grado_estimado <= 10.0