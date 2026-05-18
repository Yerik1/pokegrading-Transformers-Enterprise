"""Tests del endpoint de registro de cuenta.

Cubre la US "Registrar cuenta": happy path + cada uno de los criterios de
error específicos por campo definidos en la US.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

REGISTRO_VALIDO = {
    "correo": "ana@ejemplo.com",
    "alias": "ana_collector",
    "contrasena": "ContrasenaSegura1",
    "pais": "CR",
    "idioma_preferido": "es",
    "disclosure_aceptado": True,
}


@pytest.mark.asyncio
async def test_registro_happy_path(cliente: AsyncClient) -> None:
    resp = await cliente.post("/api/v1/usuarios/registro", json=REGISTRO_VALIDO)
    assert resp.status_code == 201

    body = resp.json()
    assert body["usuario"]["correo"] == "ana@ejemplo.com"
    assert body["usuario"]["rol"] == "submitter"
    assert body["usuario"]["pais"] == "CR"
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]
    assert body["tokens"]["token_type"] == "bearer"
    assert "X-Correlation-Id" in resp.headers


@pytest.mark.asyncio
async def test_registro_correo_duplicado(cliente: AsyncClient) -> None:
    await cliente.post("/api/v1/usuarios/registro", json=REGISTRO_VALIDO)
    resp = await cliente.post("/api/v1/usuarios/registro", json=REGISTRO_VALIDO)

    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "correo_duplicado"
    assert body["campo"] == "correo"


@pytest.mark.asyncio
async def test_registro_password_corta(cliente: AsyncClient) -> None:
    payload = {**REGISTRO_VALIDO, "contrasena": "Ab1"}
    resp = await cliente.post("/api/v1/usuarios/registro", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"] == "password_muy_corta"


@pytest.mark.asyncio
async def test_registro_password_sin_mayuscula(cliente: AsyncClient) -> None:
    payload = {**REGISTRO_VALIDO, "contrasena": "contrasenasegura1"}
    resp = await cliente.post("/api/v1/usuarios/registro", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"] == "password_sin_mayuscula"


@pytest.mark.asyncio
async def test_registro_password_sin_digito(cliente: AsyncClient) -> None:
    payload = {**REGISTRO_VALIDO, "contrasena": "ContrasenaSegura"}
    resp = await cliente.post("/api/v1/usuarios/registro", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"] == "password_sin_digito"


@pytest.mark.asyncio
async def test_registro_pais_no_soportado(cliente: AsyncClient) -> None:
    payload = {**REGISTRO_VALIDO, "pais": "US"}
    resp = await cliente.post("/api/v1/usuarios/registro", json=payload)
    assert resp.status_code == 422
    assert resp.json()["campo"] == "pais"


@pytest.mark.asyncio
async def test_registro_disclosure_no_aceptado(cliente: AsyncClient) -> None:
    payload = {**REGISTRO_VALIDO, "disclosure_aceptado": False}
    resp = await cliente.post("/api/v1/usuarios/registro", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"] == "disclosure_no_aceptado"


@pytest.mark.asyncio
async def test_registro_dominio_bloqueado(cliente: AsyncClient) -> None:
    payload = {**REGISTRO_VALIDO, "correo": "ana@mailinator.com"}
    resp = await cliente.post("/api/v1/usuarios/registro", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"] == "dominio_bloqueado"


@pytest.mark.asyncio
async def test_registro_correo_formato_invalido(cliente: AsyncClient) -> None:
    payload = {**REGISTRO_VALIDO, "correo": "no-es-un-correo"}
    resp = await cliente.post("/api/v1/usuarios/registro", json=payload)
    assert resp.status_code == 422
    assert resp.json()["campo"] == "correo"
