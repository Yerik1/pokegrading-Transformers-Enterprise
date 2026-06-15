"""Algoritmo de búsqueda rápida de cartas por hash perceptual (phash).

Implementa la Etapa 1a del flujo de identificación:
- Calcula el phash de la imagen recibida con imagehash.
- Compara contra los phashes pre-computados del catálogo.
- Devuelve los top 3 candidatos con su score de confianza.
- Si el candidato top supera el umbral, se acepta automáticamente.

El score de confianza se deriva de la distancia Hamming normalizada:
    confianza = 1 - (distancia / 64)
donde 64 es el número de bits del phash.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import imagehash
from PIL import Image

from pokegrading.compartido.logging import obtener_logger

logger = obtener_logger(__name__)

UMBRAL_ACEPTACION_AUTO: float = 0.85
BITS_PHASH: int = 64
TOP_N: int = 3


@dataclass
class CandidatoIdentificacion:
    """Resultado de un candidato en la búsqueda rápida."""

    carta_id: str
    set_codigo: str
    numero: str
    nombre: str | None
    confianza: float
    aceptado_automaticamente: bool


def calcular_phash(imagen_bytes: bytes) -> str:
    """Calcula el hash perceptual de una imagen.

    Args:
        imagen_bytes: bytes crudos de la imagen.

    Returns:
        String hexadecimal del phash (64 bits → 16 chars hex).
    """
    img = Image.open(BytesIO(imagen_bytes))
    return str(imagehash.phash(img))


def calcular_confianza(distancia_hamming: int) -> float:
    """Convierte distancia Hamming a score de confianza 0-1.

    Args:
        distancia_hamming: número de bits diferentes entre dos phashes.

    Returns:
        Score entre 0.0 (totalmente diferente) y 1.0 (idéntico).
    """
    return round(1.0 - (distancia_hamming / BITS_PHASH), 4)


def buscar_candidatos(
    phash_consulta: str,
    entradas_catalogo: list[dict],
    *,
    umbral: float = UMBRAL_ACEPTACION_AUTO,
) -> list[CandidatoIdentificacion]:
    """Busca los top N candidatos más similares en el catálogo.

    Args:
        phash_consulta: phash de la imagen subida por el usuario.
        entradas_catalogo: lista de dicts con keys:
            carta_id, set_codigo, numero, nombre, phash_frente.
        umbral: confianza mínima para aceptación automática.

    Returns:
        Lista de hasta TOP_N candidatos ordenados por confianza desc.
    """
    hash_consulta = imagehash.hex_to_hash(phash_consulta)

    resultados: list[tuple[float, dict]] = []

    for entrada in entradas_catalogo:
        phash_ref = entrada.get("phash_frente")
        if not phash_ref:
            continue
        try:
            hash_ref = imagehash.hex_to_hash(phash_ref)
            distancia = hash_consulta - hash_ref
            confianza = calcular_confianza(distancia)
            resultados.append((confianza, entrada))
        except Exception:
            logger.warning(
                "phash_invalido_en_catalogo",
                carta_id=entrada.get("carta_id"),
            )
            continue

    resultados.sort(key=lambda x: x[0], reverse=True)
    top = resultados[:TOP_N]

    candidatos = []
    for i, (confianza, entrada) in enumerate(top):
        aceptado = i == 0 and confianza >= umbral
        candidatos.append(
            CandidatoIdentificacion(
                carta_id=str(entrada["carta_id"]),
                set_codigo=entrada["set_codigo"],
                numero=entrada["numero"],
                nombre=entrada.get("nombre"),
                confianza=confianza,
                aceptado_automaticamente=aceptado,
            )
        )

    logger.info(
        "busqueda_rapida_completada",
        total_comparadas=len(entradas_catalogo),
        candidatos_encontrados=len(candidatos),
        confianza_top=candidatos[0].confianza if candidatos else None,
    )

    return candidatos
