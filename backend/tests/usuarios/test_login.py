"""Tests de los endpoints de login y refresh.

Cubre:
- Login happy path
- Login con credenciales inválidas (correo inexistente y contraseña incorrecta)
- Refresh happy path
- Refresh con tipo de token inválido (mandar un access token donde va refresh)
- Refresh con token corrupto
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


REGISTRO_VALIDO = {
    "correo": "lucia@ejemplo.com",
    "alias": "lucia_pkmn",
    "contrasena": "ContrasenaSegura1",
    "pais": "CR",
    "idioma_preferido": "es",
    "disclosure_aceptado": True,
}


async def _registrar(cliente: AsyncClient) -> dict:
    """Crea una cuenta y devuelve el cuerpo del response."""
    resp = await cliente.post("/api/v1/usuarios/registro", json=REGISTRO_VALIDO)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_login_happy_path(cliente: AsyncClient) -> None:
    await _registrar(cliente)
    resp = await cliente.post(
        "/api/v1/auth/login",
        json={
            "correo": REGISTRO_VALIDO["correo"],
            "contrasena": REGISTRO_VALIDO["contrasena"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["usuario"]["correo"] == REGISTRO_VALIDO["correo"]
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]
    assert body["tokens"]["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_correo_inexistente(cliente: AsyncClient) -> None:
    resp = await cliente.post(
        "/api/v1/auth/login",
        json={"correo": "nadie@ejemplo.com", "contrasena": "ContrasenaSegura1"},
    )
    assert resp.status_code == 401
    body = resp.json()
    # Mensaje genérico — no revelamos si el correo existe (defensa contra enumeración)
    assert body["error"] == "credenciales_invalidas"


@pytest.mark.asyncio
async def test_login_password_incorrecta(cliente: AsyncClient) -> None:
    await _registrar(cliente)
    resp = await cliente.post(
        "/api/v1/auth/login",
        json={
            "correo": REGISTRO_VALIDO["correo"],
            "contrasena": "ContrasenaIncorrecta1",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "credenciales_invalidas"


@pytest.mark.asyncio
async def test_refresh_happy_path(cliente: AsyncClient) -> None:
    body_registro = await _registrar(cliente)
    refresh_token = body_registro["tokens"]["refresh_token"]

    resp = await cliente.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]
    # El nuevo refresh debe ser distinto al anterior (rotación)
    assert body["tokens"]["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_refresh_con_access_token_falla(cliente: AsyncClient) -> None:
    body_registro = await _registrar(cliente)
    access_token = body_registro["tokens"]["access_token"]

    # Mandar un access token donde va un refresh debe fallar
    resp = await cliente.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "tipo_token_invalido"


@pytest.mark.asyncio
async def test_refresh_con_token_corrupto(cliente: AsyncClient) -> None:
    resp = await cliente.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "esto.no.es.un.jwt"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "token_invalido"
