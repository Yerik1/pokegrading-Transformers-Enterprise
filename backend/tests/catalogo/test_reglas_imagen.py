"""Tests de las reglas de validación de imágenes (SP3, DA-12)."""

from __future__ import annotations

import pytest

from pokegrading.compartido import imagenes as reglas
from pokegrading.compartido.errores import ErrorValidacion


def test_jpeg_valida_devuelve_mime(imagen_jpeg_valida: bytes) -> None:
    mime = reglas.validar_imagen(
        imagen_jpeg_valida,
        content_type_cliente="image/jpeg",
        campo="imagen_frente",
    )
    assert mime == "image/jpeg"


def test_png_valida_devuelve_mime(imagen_png_valida: bytes) -> None:
    mime = reglas.validar_imagen(
        imagen_png_valida,
        content_type_cliente="image/png",
        campo="imagen_frente",
    )
    assert mime == "image/png"


def test_imagen_vacia_falla() -> None:
    with pytest.raises(ErrorValidacion) as exc:
        reglas.validar_imagen(b"", content_type_cliente="image/jpeg", campo="x")
    assert exc.value.codigo == "imagen_vacia"


def test_imagen_demasiado_grande_falla() -> None:
    # JPEG válido por magic + 11 MB de relleno
    enorme = b"\xff\xd8\xff" + b"X" * (11 * 1024 * 1024)
    with pytest.raises(ErrorValidacion) as exc:
        reglas.validar_imagen(enorme, content_type_cliente="image/jpeg", campo="x")
    assert exc.value.codigo == "imagen_demasiado_grande"


def test_heic_se_rechaza_explicitamente(archivo_heic_falso: bytes) -> None:
    """SP3 lista HEIC pero el equipo decidió rechazarlo en Sprint 1."""
    with pytest.raises(ErrorValidacion) as exc:
        reglas.validar_imagen(
            archivo_heic_falso, content_type_cliente="image/heic", campo="x"
        )
    assert exc.value.codigo == "formato_heic_no_soportado"


def test_formato_no_imagen_se_rechaza(archivo_no_imagen: bytes) -> None:
    """Aunque el cliente diga 'image/jpeg' en el Content-Type, los magic
    bytes no concuerdan → rechazo (protección anti-polyglot, DA-12)."""
    with pytest.raises(ErrorValidacion) as exc:
        reglas.validar_imagen(
            archivo_no_imagen,
            content_type_cliente="image/jpeg",  # cliente miente
            campo="x",
        )
    assert exc.value.codigo == "formato_no_soportado"


def test_imagen_corrupta_se_rechaza(imagen_corrupta: bytes) -> None:
    with pytest.raises(ErrorValidacion) as exc:
        reglas.validar_imagen(
            imagen_corrupta, content_type_cliente="image/jpeg", campo="x"
        )
    assert exc.value.codigo == "imagen_corrupta"


def test_resolucion_insuficiente(imagen_pequena: bytes) -> None:
    with pytest.raises(ErrorValidacion) as exc:
        reglas.validar_imagen(
            imagen_pequena, content_type_cliente="image/jpeg", campo="x"
        )
    assert exc.value.codigo == "imagen_resolucion_insuficiente"


def test_resolucion_excesiva(imagen_enorme: bytes) -> None:
    with pytest.raises(ErrorValidacion) as exc:
        reglas.validar_imagen(
            imagen_enorme, content_type_cliente="image/jpeg", campo="x"
        )
    assert exc.value.codigo == "imagen_resolucion_excesiva"


def test_campo_se_propaga_al_error() -> None:
    with pytest.raises(ErrorValidacion) as exc:
        reglas.validar_imagen(
            b"", content_type_cliente="image/jpeg", campo="imagen_reverso"
        )
    assert exc.value.campo == "imagen_reverso"
