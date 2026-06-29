"""Tests de integración del endpoint enviar carta (US 191 + US 193).

Verifica el pipeline completo a través del endpoint HTTP, usando
SQLite en memoria y AlmacenamientoEnMemoria como en los otros tests.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.seguridad import crear_token, hashear_password
from pokegrading.negocio.evaluaciones.modelos import GradingBaseline
from pokegrading.negocio.usuarios.modelos import Usuario
from pokegrading.negocio.usuarios.tipos import Idioma, Pais, Rol

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _imagen_con_carta_bytes() -> bytes:
    """Imagen sintética con carta sobre fondo blanco — pasa el pipeline."""
    img = Image.new("RGB", (800, 1100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([80, 80, 720, 1020], fill=(50, 50, 50), outline=(0, 0, 0), width=10)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _imagen_pequeña_bytes() -> bytes:
    """Imagen de resolución insuficiente."""
    img = Image.new("RGB", (300, 400), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def _crear_submitter(sesion: AsyncSession) -> Usuario:
    usuario = Usuario(
        correo=f"submitter_{uuid.uuid4().hex[:6]}@test.com",
        alias="Submitter Test",
        hash_password=hashear_password("Password1"),
        pais=Pais.CR,
        idioma_preferido=Idioma.ES,
        rol=Rol.SUBMITTER,
        disclosure_aceptado=True,
        disclosure_version="v1.0",
        disclosure_aceptado_en=datetime.now(UTC),
    )
    sesion.add(usuario)
    await sesion.commit()
    await sesion.refresh(usuario)
    return usuario


async def _crear_baseline_global(sesion: AsyncSession) -> GradingBaseline:
    baseline = GradingBaseline(
        set_codigo=None,
        acabado=None,
        referencia_centering=0.7,
        referencia_corners=0.7,
        referencia_edges=0.7,
        referencia_surface=0.7,
        tamano_muestra=0,
        version_algoritmo="v1.0",
    )
    sesion.add(baseline)
    await sesion.commit()
    await sesion.refresh(baseline)
    return baseline


def _token_de(usuario: Usuario) -> str:
    return crear_token(
        str(usuario.id),
        tipo="access",
        extra_claims={"rol": usuario.rol.value},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enviar_carta_sin_autenticacion_devuelve_401(
    cliente: AsyncClient,
    _sesion: AsyncSession,
) -> None:
    """Sin token → 401."""
    imagen = _imagen_pequeña_bytes()
    resp = await cliente.post(
        "/api/v1/evaluaciones/enviar",
        files={
            "imagen_frente": ("f.jpg", imagen, "image/jpeg"),
            "imagen_reverso": ("r.jpg", imagen, "image/jpeg"),
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_enviar_carta_imagen_pequena_devuelve_422(
    cliente: AsyncClient,
    _sesion: AsyncSession,
) -> None:
    """Imagen de resolución insuficiente → 422."""
    usuario = await _crear_submitter(_sesion)
    token = _token_de(usuario)
    imagen = _imagen_pequeña_bytes()

    resp = await cliente.post(
        "/api/v1/evaluaciones/enviar",
        files={
            "imagen_frente": ("f.jpg", imagen, "image/jpeg"),
            "imagen_reverso": ("r.jpg", imagen, "image/jpeg"),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "imagen_resolucion_insuficiente"


@pytest.mark.asyncio
async def test_enviar_carta_pipeline_devuelve_202_con_estado(
    cliente: AsyncClient,
    _sesion: AsyncSession,
) -> None:
    """Pipeline completo con imagen válida → 202 con estado del pipeline."""
    usuario = await _crear_submitter(_sesion)
    await _crear_baseline_global(_sesion)
    token = _token_de(usuario)
    imagen = _imagen_con_carta_bytes()

    resp = await cliente.post(
        "/api/v1/evaluaciones/enviar",
        files={
            "imagen_frente": ("f.jpg", imagen, "image/jpeg"),
            "imagen_reverso": ("r.jpg", imagen, "image/jpeg"),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    datos = resp.json()
    assert "identificador_evaluacion" in datos
    assert datos["estado"] in ("completada", "revision_manual", "rechazada")
    assert "iq_score_frente" in datos
    assert "iq_score_reverso" in datos


@pytest.mark.asyncio
async def test_enviar_carta_completada_tiene_campos_sp4(
    cliente: AsyncClient,
    _sesion: AsyncSession,
) -> None:
    """Si el pipeline completa, la respuesta incluye campos del SP4."""
    usuario = await _crear_submitter(_sesion)
    await _crear_baseline_global(_sesion)
    token = _token_de(usuario)
    imagen = _imagen_con_carta_bytes()

    resp = await cliente.post(
        "/api/v1/evaluaciones/enviar",
        files={
            "imagen_frente": ("f.jpg", imagen, "image/jpeg"),
            "imagen_reverso": ("r.jpg", imagen, "image/jpeg"),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    datos = resp.json()

    # Los campos del SP4 siempre están presentes en el schema
    assert "grado_estimado" in datos
    assert "banda_incertidumbre" in datos
    assert "subgrade_centering" in datos
    assert "subgrade_corners" in datos
    assert "subgrade_edges" in datos
    assert "subgrade_surface" in datos
    assert "version_algoritmo_grading" in datos

    # Si completó, el grado debe estar en escala válida
    if datos["estado"] == "completada":
        assert datos["grado_estimado"] is not None
        assert 1.0 <= datos["grado_estimado"] <= 10.0
