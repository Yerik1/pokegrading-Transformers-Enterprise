"""Tests de idempotencia del pipeline de evaluación (US 193).

Bug original (#2): la clave se calculaba sobre las claves de blob
(`evaluaciones/{evaluacion_id}/...`), que son distintas en cada envío
porque incluyen un `evaluacion_id` nuevo (uuid4()). Dos envíos de la
MISMA carta nunca producían la misma clave, así que la idempotencia
nunca se disparaba.

Bug derivado del primer fix (#2b): al corregir el cálculo de la clave
para que SÍ coincida entre reintentos reales, se expuso un problema de
orden de operaciones dentro de `CalificarCartaService`: se asignaba la
clave al registro nuevo ANTES de consultar si ya existía un duplicado.
Como `clave_idempotencia` es `unique=True` en BD, el segundo envío
disparaba un IntegrityError. Se corrigió invirtiendo el orden.

Bug derivado #2c (este fix): aun con #2b corregido, el reintento SEGUÍA
creando una fila nueva en `evaluaciones` (quedaba atascada en
`calificando`, sin clave ni grado) porque el chequeo de idempotencia
vivía DENTRO de `CalificarCartaService`, que corre después de que
`EnviarCartaService` ya subió las imágenes y creó el registro. Se movió
el chequeo a `PipelineEvaluacionService`, ANTES de tocar Blob Storage o
la base de datos, para que un reintento real no cree ningún registro
nuevo. El chequeo dentro de `CalificarCartaService` se mantiene como
red de seguridad (condición de carrera entre envíos paralelos), pero
ya no es la primera línea de defensa.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.seguridad import crear_token, hashear_password
from pokegrading.negocio.evaluaciones.modelos import Evaluacion, GradingBaseline
from pokegrading.negocio.evaluaciones.servicio_calificar import CalificarCartaService
from pokegrading.negocio.usuarios.modelos import Usuario
from pokegrading.negocio.usuarios.tipos import Idioma, Pais, Rol

CONTENEDOR = "cartas-referencia"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _imagen_con_carta_bytes() -> bytes:
    """Imagen sintética con carta sobre fondo blanco — pasa el pipeline completo."""
    img = Image.new("RGB", (800, 1100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([80, 80, 720, 1020], fill=(50, 50, 50), outline=(0, 0, 0), width=10)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _evaluacion_con_claves_unicas(
    submitter_id: uuid.UUID,
) -> tuple[Evaluacion, str, str]:
    """Construye una Evaluacion con rutas de blob únicas (como en un
    envío real: cada uno tiene su propio `evaluacion_id`).
    """
    evaluacion_id = uuid.uuid4()
    clave_frente = f"evaluaciones/{evaluacion_id}/frente.jpg"
    clave_reverso = f"evaluaciones/{evaluacion_id}/reverso.jpg"
    evaluacion = Evaluacion(
        id=evaluacion_id,
        identificador_evaluacion=f"EV-TEST-{evaluacion_id.hex[:6]}",
        submitter_id=submitter_id,
        estado="calificando",
        url_imagen_frente="memory://x",
        clave_blob_frente=clave_frente,
        url_imagen_reverso="memory://x",
        clave_blob_reverso=clave_reverso,
    )
    return evaluacion, clave_frente, clave_reverso


# ---------------------------------------------------------------------------
# Tests del cálculo de la clave (rápidos, sin pasar por el pipeline)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_misma_carta_mismo_submitter_misma_clave(
    _sesion: AsyncSession, _almacenamiento
) -> None:
    """Dos envíos de la MISMA carta (mismo contenido de imagen) por el
    mismo submitter deben producir la MISMA clave de idempotencia,
    aunque las rutas de blob sean distintas.
    """
    usuario = await _crear_submitter(_sesion)
    bytes_frente = b"contenido-real-frente-fijo"
    bytes_reverso = b"contenido-real-reverso-fijo"

    eval_a, clave_f_a, clave_r_a = _evaluacion_con_claves_unicas(usuario.id)
    eval_b, clave_f_b, clave_r_b = _evaluacion_con_claves_unicas(usuario.id)

    await _almacenamiento.guardar(CONTENEDOR, clave_f_a, bytes_frente, "image/jpeg")
    await _almacenamiento.guardar(CONTENEDOR, clave_r_a, bytes_reverso, "image/jpeg")
    await _almacenamiento.guardar(CONTENEDOR, clave_f_b, bytes_frente, "image/jpeg")
    await _almacenamiento.guardar(CONTENEDOR, clave_r_b, bytes_reverso, "image/jpeg")

    assert clave_f_a != clave_f_b  # confirma la premisa del bug original

    servicio = CalificarCartaService(_sesion, _almacenamiento)
    clave_idemp_a = await servicio._calcular_clave_idempotencia(eval_a)
    clave_idemp_b = await servicio._calcular_clave_idempotencia(eval_b)

    assert clave_idemp_a == clave_idemp_b


@pytest.mark.asyncio
async def test_cartas_distintas_producen_claves_distintas(
    _sesion: AsyncSession, _almacenamiento
) -> None:
    """Control negativo: contenido distinto debe seguir produciendo
    claves distintas.
    """
    usuario = await _crear_submitter(_sesion)

    eval_a, clave_f_a, clave_r_a = _evaluacion_con_claves_unicas(usuario.id)
    eval_b, clave_f_b, clave_r_b = _evaluacion_con_claves_unicas(usuario.id)

    await _almacenamiento.guardar(
        CONTENEDOR, clave_f_a, b"carta-1-frente", "image/jpeg"
    )
    await _almacenamiento.guardar(
        CONTENEDOR, clave_r_a, b"carta-1-reverso", "image/jpeg"
    )
    await _almacenamiento.guardar(
        CONTENEDOR, clave_f_b, b"carta-2-frente", "image/jpeg"
    )
    await _almacenamiento.guardar(
        CONTENEDOR, clave_r_b, b"carta-2-reverso", "image/jpeg"
    )

    servicio = CalificarCartaService(_sesion, _almacenamiento)
    clave_idemp_a = await servicio._calcular_clave_idempotencia(eval_a)
    clave_idemp_b = await servicio._calcular_clave_idempotencia(eval_b)

    assert clave_idemp_a != clave_idemp_b


@pytest.mark.asyncio
async def test_distinto_submitter_misma_carta_clave_distinta(
    _sesion: AsyncSession, _almacenamiento
) -> None:
    """Dos submitters distintos enviando la MISMA imagen no deben
    compartir clave de idempotencia.
    """
    usuario_a = await _crear_submitter(_sesion)
    usuario_b = await _crear_submitter(_sesion)
    bytes_frente = b"misma-imagen-frente"
    bytes_reverso = b"misma-imagen-reverso"

    eval_a, clave_f_a, clave_r_a = _evaluacion_con_claves_unicas(usuario_a.id)
    eval_b, clave_f_b, clave_r_b = _evaluacion_con_claves_unicas(usuario_b.id)

    await _almacenamiento.guardar(CONTENEDOR, clave_f_a, bytes_frente, "image/jpeg")
    await _almacenamiento.guardar(CONTENEDOR, clave_r_a, bytes_reverso, "image/jpeg")
    await _almacenamiento.guardar(CONTENEDOR, clave_f_b, bytes_frente, "image/jpeg")
    await _almacenamiento.guardar(CONTENEDOR, clave_r_b, bytes_reverso, "image/jpeg")

    servicio = CalificarCartaService(_sesion, _almacenamiento)
    clave_idemp_a = await servicio._calcular_clave_idempotencia(eval_a)
    clave_idemp_b = await servicio._calcular_clave_idempotencia(eval_b)

    assert clave_idemp_a != clave_idemp_b


# ---------------------------------------------------------------------------
# Test end-to-end: idempotencia TEMPRANA, sin filas duplicadas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reenvio_real_misma_carta_no_crea_fila_duplicada(
    cliente: AsyncClient,
    _sesion: AsyncSession,
) -> None:
    """Reenviar la MISMA carta dos veces por el endpoint HTTP real (sin
    mocks) no debe crear una segunda fila en `evaluaciones`. El chequeo
    de idempotencia ahora corre ANTES de subir nada a Blob Storage o
    crear el registro — un reintento real es indistinguible, para la
    base de datos, de no haber pasado nunca.
    """
    usuario = await _crear_submitter(_sesion)
    await _crear_baseline_global(_sesion)
    token = _token_de(usuario)
    imagen = _imagen_con_carta_bytes()

    resp1 = await cliente.post(
        "/api/v1/evaluaciones/enviar",
        files={
            "imagen_frente": ("f.jpg", imagen, "image/jpeg"),
            "imagen_reverso": ("r.jpg", imagen, "image/jpeg"),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 202
    datos1 = resp1.json()

    # Reenvío exacto de la misma carta, mismo submitter.
    resp2 = await cliente.post(
        "/api/v1/evaluaciones/enviar",
        files={
            "imagen_frente": ("f.jpg", imagen, "image/jpeg"),
            "imagen_reverso": ("r.jpg", imagen, "image/jpeg"),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 202
    datos2 = resp2.json()

    if datos1["estado"] == "completada":
        assert datos2["estado"] == "completada"
        assert datos2["grado_estimado"] == datos1["grado_estimado"]
        # El reintento devuelve el MISMO identificador que el original,
        # no uno nuevo — no hay una segunda evaluación "propia".
        assert datos2["identificador_evaluacion"] == datos1["identificador_evaluacion"]

        # En BD: una sola fila. Antes de este fix quedaban dos (la
        # segunda atascada en 'calificando' sin clave ni grado).
        resultado = await _sesion.execute(select(Evaluacion))
        evaluaciones = resultado.scalars().all()
        assert len(evaluaciones) == 1, (
            "El reintento no debería crear una fila nueva en absoluto; "
            f"se encontraron {len(evaluaciones)} filas."
        )


@pytest.mark.asyncio
async def test_envios_de_cartas_distintas_si_crean_filas_separadas(
    cliente: AsyncClient,
    _sesion: AsyncSession,
) -> None:
    """Control negativo: dos cartas con contenido DISTINTO deben seguir
    generando dos filas separadas — la idempotencia no debe fusionar
    evaluaciones que no son reintentos reales.
    """
    usuario = await _crear_submitter(_sesion)
    await _crear_baseline_global(_sesion)
    token = _token_de(usuario)

    imagen_a = _imagen_con_carta_bytes()
    # Segunda imagen con un color de fondo distinto -> contenido distinto.
    img_b = Image.new("RGB", (800, 1100), color=(240, 240, 255))
    draw = ImageDraw.Draw(img_b)
    draw.rectangle([80, 80, 720, 1020], fill=(40, 40, 40), outline=(0, 0, 0), width=10)
    buf = io.BytesIO()
    img_b.save(buf, format="JPEG", quality=95)
    imagen_b = buf.getvalue()

    await cliente.post(
        "/api/v1/evaluaciones/enviar",
        files={
            "imagen_frente": ("f.jpg", imagen_a, "image/jpeg"),
            "imagen_reverso": ("r.jpg", imagen_a, "image/jpeg"),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    await cliente.post(
        "/api/v1/evaluaciones/enviar",
        files={
            "imagen_frente": ("f.jpg", imagen_b, "image/jpeg"),
            "imagen_reverso": ("r.jpg", imagen_b, "image/jpeg"),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resultado = await _sesion.execute(select(Evaluacion))
    evaluaciones = resultado.scalars().all()
    assert len(evaluaciones) == 2
