"""Tests del endpoint `POST /api/v1/catalogo/cartas`.

Cubre los criterios principales de la US "Agregar carta al catálogo":
- Happy path
- Duplicado de identity tuple → 409
- Falta de auth → 401
- Rol insuficiente (Submitter) → 403
- Validación de datos incorrectos
- Validación de imagen
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.seguridad import crear_token, hashear_password
from pokegrading.negocio.usuarios.modelos import Usuario
from pokegrading.negocio.usuarios.tipos import Idioma, Pais, Rol


async def _crear_admin_directo(sesion: AsyncSession, rol: Rol = Rol.ADMIN) -> Usuario:
    """Crea un admin/superadmin saltando el endpoint de registro.

    El registro público solo crea Submitters; los roles administrativos
    se crean por CLI o, en tests, directo en la BD.
    """
    admin = Usuario(
        correo=f"{rol.value}_{uuid.uuid4().hex[:6]}@test.com",
        alias=rol.value,
        hash_password=hashear_password("AdminSeguro123"),
        pais=Pais.CR,
        idioma_preferido=Idioma.ES,
        rol=rol,
        disclosure_aceptado=True,
        disclosure_version="v1.0",
        disclosure_aceptado_en=datetime.now(UTC),
    )
    sesion.add(admin)
    await sesion.commit()
    await sesion.refresh(admin)
    return admin


def _token_de(usuario: Usuario) -> str:
    return crear_token(
        str(usuario.id),
        tipo="access",
        extra_claims={"rol": usuario.rol.value},
    )


def _datos_carta_base() -> dict:
    return {
        "set_codigo": "BASE",
        "numero": "4",
        "edicion": "1st_edition",
        "idioma": "EN",
        "acabado": "holo",
        "nombre": "Charizard",
        "rareza": "holo_rare",
        "tipo": "fire",
        "hp": 120,
        "ilustrador": "Mitsuhiro Arita",
        "anio_impresion": 1999,
    }


@pytest.mark.asyncio
async def test_agregar_carta_happy_path(
    cliente: AsyncClient,
    _sesion: AsyncSession,
    imagen_jpeg_valida: bytes,
) -> None:
    admin = await _crear_admin_directo(_sesion)
    token = _token_de(admin)

    resp = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": json.dumps(_datos_carta_base())},
        files={
            "imagen_frente": ("frente.jpg", imagen_jpeg_valida, "image/jpeg"),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["set_codigo"] == "BASE"
    assert body["numero"] == "4"
    assert body["nombre"] == "Charizard"
    assert body["hp"] == 120
    assert body["url_imagen_frente"].startswith("memory://")
    assert body["url_imagen_reverso"] is None
    assert body["creada_por_id"] == str(admin.id)


@pytest.mark.asyncio
async def test_agregar_carta_con_reverso(
    cliente: AsyncClient,
    _sesion: AsyncSession,
    imagen_jpeg_valida: bytes,
    imagen_png_valida: bytes,
) -> None:
    admin = await _crear_admin_directo(_sesion)
    token = _token_de(admin)

    resp = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": json.dumps(_datos_carta_base())},
        files=[
            ("imagen_frente", ("f.jpg", imagen_jpeg_valida, "image/jpeg")),
            ("imagen_reverso", ("r.png", imagen_png_valida, "image/png")),
        ],
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["url_imagen_reverso"] is not None
    assert body["url_imagen_reverso"].startswith("memory://")


@pytest.mark.asyncio
async def test_superadmin_tambien_puede_agregar(
    cliente: AsyncClient,
    _sesion: AsyncSession,
    imagen_jpeg_valida: bytes,
) -> None:
    superadmin = await _crear_admin_directo(_sesion, rol=Rol.SUPERADMIN)
    token = _token_de(superadmin)

    resp = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": json.dumps(_datos_carta_base())},
        files={"imagen_frente": ("f.jpg", imagen_jpeg_valida, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_carta_duplicada_devuelve_409(
    cliente: AsyncClient,
    _sesion: AsyncSession,
    imagen_jpeg_valida: bytes,
) -> None:
    admin = await _crear_admin_directo(_sesion)
    token = _token_de(admin)
    datos = _datos_carta_base()

    # Primera creación: 201
    r1 = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": json.dumps(datos)},
        files={"imagen_frente": ("f.jpg", imagen_jpeg_valida, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201

    # Segunda con misma identity tuple: 409
    r2 = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": json.dumps(datos)},
        files={"imagen_frente": ("f.jpg", imagen_jpeg_valida, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 409
    assert r2.json()["error"] == "carta_duplicada"
    assert r2.json()["campo"] == "set_codigo"


@pytest.mark.asyncio
async def test_sin_token_devuelve_401(
    cliente: AsyncClient,
    imagen_jpeg_valida: bytes,
) -> None:
    resp = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": json.dumps(_datos_carta_base())},
        files={"imagen_frente": ("f.jpg", imagen_jpeg_valida, "image/jpeg")},
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "token_faltante"


@pytest.mark.asyncio
async def test_submitter_no_puede_agregar_carta(
    cliente: AsyncClient,
    imagen_jpeg_valida: bytes,
) -> None:
    """Un Submitter (rol no-admin) recibe 403."""
    # Registrarse como Submitter
    payload = {
        "correo": "sub@test.com",
        "alias": "sub",
        "contrasena": "Submitter12345",
        "pais": "CR",
        "idioma_preferido": "es",
        "disclosure_aceptado": True,
    }
    reg = await cliente.post("/api/v1/usuarios/registro", json=payload)
    token = reg.json()["tokens"]["access_token"]

    resp = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": json.dumps(_datos_carta_base())},
        files={"imagen_frente": ("f.jpg", imagen_jpeg_valida, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "rol_insuficiente"


@pytest.mark.asyncio
async def test_datos_json_invalido(
    cliente: AsyncClient,
    _sesion: AsyncSession,
    imagen_jpeg_valida: bytes,
) -> None:
    admin = await _crear_admin_directo(_sesion)
    token = _token_de(admin)

    resp = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": "esto no es JSON {{{"},
        files={"imagen_frente": ("f.jpg", imagen_jpeg_valida, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "datos_json_invalido"


@pytest.mark.asyncio
async def test_idioma_invalido(
    cliente: AsyncClient,
    _sesion: AsyncSession,
    imagen_jpeg_valida: bytes,
) -> None:
    admin = await _crear_admin_directo(_sesion)
    token = _token_de(admin)
    datos = _datos_carta_base()
    datos["idioma"] = "XX"  # no es un valor del enum

    resp = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": json.dumps(datos)},
        files={"imagen_frente": ("f.jpg", imagen_jpeg_valida, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["campo"] == "idioma"


@pytest.mark.asyncio
async def test_imagen_pequena_rechazada(
    cliente: AsyncClient,
    _sesion: AsyncSession,
    imagen_pequena: bytes,
) -> None:
    admin = await _crear_admin_directo(_sesion)
    token = _token_de(admin)

    resp = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": json.dumps(_datos_carta_base())},
        files={"imagen_frente": ("f.jpg", imagen_pequena, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "imagen_resolucion_insuficiente"


@pytest.mark.asyncio
async def test_heic_rechazado_en_endpoint(
    cliente: AsyncClient,
    _sesion: AsyncSession,
    archivo_heic_falso: bytes,
) -> None:
    admin = await _crear_admin_directo(_sesion)
    token = _token_de(admin)

    resp = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": json.dumps(_datos_carta_base())},
        files={"imagen_frente": ("f.heic", archivo_heic_falso, "image/heic")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "formato_heic_no_soportado"


@pytest.mark.asyncio
async def test_hp_fuera_de_rango(
    cliente: AsyncClient,
    _sesion: AsyncSession,
    imagen_jpeg_valida: bytes,
) -> None:
    admin = await _crear_admin_directo(_sesion)
    token = _token_de(admin)
    datos = _datos_carta_base()
    datos["hp"] = 9999  # fuera del rango 30-340

    resp = await cliente.post(
        "/api/v1/catalogo/cartas",
        data={"datos": json.dumps(datos)},
        files={"imagen_frente": ("f.jpg", imagen_jpeg_valida, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["campo"] == "hp"
