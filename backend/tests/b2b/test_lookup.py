"""Tests de integración del API B2B."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pokegrading.compartido.seguridad import hashear_password
from pokegrading.negocio.b2b.modelos import B2BCuenta, B2BRateLimit
from pokegrading.negocio.catalogo.modelos import Carta
from pokegrading.negocio.catalogo.tipos import Acabado, Edicion, IdiomaCarta
from pokegrading.negocio.usuarios.modelos import Usuario
from pokegrading.negocio.usuarios.tipos import Idioma, Pais, Rol

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_API_KEY_VALIDA = "pg_b2b_testkey0000000000000000000000000000000000000000000000000000"
_API_KEY_HASH = hashlib.sha256(_API_KEY_VALIDA.encode()).hexdigest()


def _usuario_b2b(_sesion: AsyncSession) -> Usuario:
    u = Usuario(
        correo="tienda@b2b.com",
        alias="TiendaTest",
        hash_password=hashear_password("Temporal1"),
        pais=Pais.CR,
        idioma_preferido=Idioma.ES,
        rol=Rol.B2B_SERVICE_ACCOUNT,
        disclosure_aceptado=True,
        disclosure_version="v1.0",
        disclosure_aceptado_en=datetime.now(UTC),
    )
    _sesion.add(u)
    return u


def _cuenta_b2b(usuario_id: uuid.UUID, _sesion: AsyncSession, **kwargs) -> B2BCuenta:
    defaults = dict(
        nombre_tienda="Tienda Test",
        api_key_hash=_API_KEY_HASH,
        api_key_prefijo=_API_KEY_VALIDA[7:15],
        activa=True,
        suspendida=False,
        limite_cartas_mes=100,
        ventana_idempotencia_segundos=300,
        usuario_id=usuario_id,
    )
    defaults.update(kwargs)
    cuenta = B2BCuenta(**defaults)
    _sesion.add(cuenta)
    return cuenta


def _carta(
    _sesion: AsyncSession, set_codigo: str = "BASE1", numero: str = "4"
) -> Carta:
    carta = Carta(
        set_codigo=set_codigo,
        numero=numero,
        edicion=Edicion.FIRST_EDITION,
        idioma=IdiomaCarta.EN,
        acabado=Acabado.HOLO,
        nombre="Charizard",
        url_imagen_frente="https://blob.test/frente.jpg",
        clave_blob_frente="cartas/test/frente.jpg",
        creada_por_id=uuid.uuid4(),
    )
    _sesion.add(carta)
    return carta


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def cuenta_activa(_sesion: AsyncSession) -> B2BCuenta:
    """Crea un usuario B2B y su cuenta activa en BD."""
    usuario = _usuario_b2b(_sesion)
    await _sesion.flush()
    cuenta = _cuenta_b2b(usuario.id, _sesion)
    await _sesion.flush()
    return cuenta


@pytest.fixture
async def carta_en_catalogo(_sesion: AsyncSession) -> Carta:
    """Inserta una carta BASE1/4 en el catálogo."""
    carta = _carta(_sesion)
    await _sesion.flush()
    return carta


# ---------------------------------------------------------------------------
# Tests: autenticación
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_key_invalida_devuelve_401(
    cliente: AsyncClient,
    cuenta_activa: B2BCuenta,
):
    res = await cliente.post(
        "/api/b2b/v1/catalogo/lookup",
        json={"cartas": [{"set_codigo": "BASE1", "numero": "4"}]},
        headers={"X-Api-Key": "pg_b2b_clave_falsa"},
    )
    assert res.status_code == 401
    body = res.json()
    assert body["error"] == "api_key_invalida"
    assert "correlation_id" in body


@pytest.mark.asyncio
async def test_cuenta_suspendida_devuelve_401(
    cliente: AsyncClient,
    _sesion: AsyncSession,
):
    usuario = _usuario_b2b(_sesion)
    await _sesion.flush()
    _cuenta_b2b(
        usuario.id,
        _sesion,
        suspendida=True,
        motivo_suspension="Fraude detectado",
    )
    await _sesion.commit()

    res = await cliente.post(
        "/api/b2b/v1/catalogo/lookup",
        json={"cartas": [{"set_codigo": "BASE1", "numero": "4"}]},
        headers={"X-Api-Key": _API_KEY_VALIDA},
    )
    assert res.status_code == 401
    body = res.json()
    assert body["error"] == "cuenta_b2b_suspendida"


# ---------------------------------------------------------------------------
# Tests: lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_carta_cubierta(
    cliente: AsyncClient,
    cuenta_activa: B2BCuenta,
    carta_en_catalogo: Carta,
):
    res = await cliente.post(
        "/api/b2b/v1/catalogo/lookup",
        json={"cartas": [{"set_codigo": "BASE1", "numero": "4"}]},
        headers={"X-Api-Key": _API_KEY_VALIDA},
    )
    assert res.status_code == 200
    resultado = res.json()["resultados"][0]
    assert resultado["estado"] == "cubierta"
    assert resultado["carta"]["set_codigo"] == "BASE1"
    assert resultado["carta"]["numero"] == "4"


@pytest.mark.asyncio
async def test_carta_no_cubierta(
    cliente: AsyncClient,
    cuenta_activa: B2BCuenta,
):
    res = await cliente.post(
        "/api/b2b/v1/catalogo/lookup",
        json={"cartas": [{"set_codigo": "INEXISTENTE", "numero": "999"}]},
        headers={"X-Api-Key": _API_KEY_VALIDA},
    )
    assert res.status_code == 200
    resultado = res.json()["resultados"][0]
    assert resultado["estado"] == "no_cubierta"


@pytest.mark.asyncio
async def test_parametros_invalidos_no_bloquea_otras_cartas(
    cliente: AsyncClient,
    cuenta_activa: B2BCuenta,
    carta_en_catalogo: Carta,
    _sesion: AsyncSession,
):
    res = await cliente.post(
        "/api/b2b/v1/catalogo/lookup",
        json={
            "cartas": [
                {"set_codigo": "BASE1", "numero": "4", "acabado": "NO_EXISTE"},
                {"set_codigo": "BASE1", "numero": "4"},
            ]
        },
        headers={"X-Api-Key": _API_KEY_VALIDA},
    )
    assert res.status_code == 200
    resultados = res.json()["resultados"]
    assert resultados[0]["estado"] == "parametros_invalidos"
    assert resultados[0]["campo"] == "acabado"
    assert resultados[1]["estado"] == "cubierta"


@pytest.mark.asyncio
async def test_multiples_coincidencias(
    cliente: AsyncClient,
    cuenta_activa: B2BCuenta,
    _sesion: AsyncSession,
):
    c1 = Carta(
        set_codigo="SWSH01",
        numero="1",
        edicion=Edicion.UNLIMITED,
        idioma=IdiomaCarta.EN,
        acabado=Acabado.HOLO,
        url_imagen_frente="https://blob.test/1.jpg",
        clave_blob_frente="t/1.jpg",
        creada_por_id=uuid.uuid4(),
    )
    c2 = Carta(
        set_codigo="SWSH01",
        numero="1",
        edicion=Edicion.UNLIMITED,
        idioma=IdiomaCarta.EN,
        acabado=Acabado.NON_HOLO,
        url_imagen_frente="https://blob.test/2.jpg",
        clave_blob_frente="t/2.jpg",
        creada_por_id=uuid.uuid4(),
    )
    _sesion.add_all([c1, c2])
    await _sesion.commit()

    res = await cliente.post(
        "/api/b2b/v1/catalogo/lookup",
        json={"cartas": [{"set_codigo": "SWSH01", "numero": "1"}]},
        headers={"X-Api-Key": _API_KEY_VALIDA},
    )
    assert res.status_code == 200
    resultado = res.json()["resultados"][0]
    assert resultado["estado"] == "coincidencia_multiple"
    assert len(resultado["candidatos"]) == 2
    ids = [c["carta_id"] for c in resultado["candidatos"]]
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Tests: idempotencia
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reintento_idempotente_devuelve_misma_respuesta(
    cliente: AsyncClient,
    cuenta_activa: B2BCuenta,
    carta_en_catalogo: Carta,
):
    payload = {
        "cartas": [{"set_codigo": "BASE1", "numero": "4"}],
        "identificador_solicitud": "req-tienda-001",
    }
    headers = {"X-Api-Key": _API_KEY_VALIDA}

    res1 = await cliente.post(
        "/api/b2b/v1/catalogo/lookup", json=payload, headers=headers
    )
    res2 = await cliente.post(
        "/api/b2b/v1/catalogo/lookup", json=payload, headers=headers
    )

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res2.json()["es_reintento"] is True
    assert res1.json()["resultados"] == res2.json()["resultados"]


# ---------------------------------------------------------------------------
# Tests: rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_excedido_devuelve_403(
    cliente: AsyncClient,
    cuenta_activa: B2BCuenta,
    _sesion: AsyncSession,
):
    ahora = datetime.now(UTC)
    rl = B2BRateLimit(
        cuenta_id=cuenta_activa.id,
        anio=ahora.year,
        mes=ahora.month,
        cartas_consultadas=100,  # == limite_cartas_mes de la fixture
    )
    _sesion.add(rl)
    await _sesion.commit()

    res = await cliente.post(
        "/api/b2b/v1/catalogo/lookup",
        json={"cartas": [{"set_codigo": "BASE1", "numero": "4"}]},
        headers={"X-Api-Key": _API_KEY_VALIDA},
    )
    assert res.status_code == 403
    body = res.json()
    assert body["error"] == "cuota_mensual_excedida"
    assert "reintentar_en" in body
