"""Enums del dominio de catálogo.

Los valores son los listados canónicos descritos en la US "Agregar carta
al catálogo" y en la wiki técnica.
"""

from __future__ import annotations

from enum import StrEnum


class Edicion(StrEnum):
    """Edición de la impresión de la carta.

    La US menciona "1st Edition, Unlimited, Shadowless, etc." — empezamos
    con estos 3. Si en el futuro hace falta otra edición, se agrega aquí
    + se hace migración Alembic con `ALTER TYPE ... ADD VALUE`.
    """

    FIRST_EDITION = "1st_edition"
    UNLIMITED = "unlimited"
    SHADOWLESS = "shadowless"


class Acabado(StrEnum):
    """Acabado físico de la carta."""

    HOLO = "holo"
    REVERSE_HOLO = "reverse_holo"
    FULL_ART = "full_art"
    NON_HOLO = "non_holo"


class Rareza(StrEnum):
    """Rareza canónica del TCG (dada explícitamente por la US)."""

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    HOLO_RARE = "holo_rare"
    ULTRA_RARE = "ultra_rare"
    SECRET_RARE = "secret_rare"


class TipoPokemon(StrEnum):
    """11 tipos oficiales del Pokémon TCG.

    Notar: en el TCG existen 11 tipos (a diferencia de los 18 del videojuego).
    """

    GRASS = "grass"
    FIRE = "fire"
    WATER = "water"
    LIGHTNING = "lightning"
    PSYCHIC = "psychic"
    FIGHTING = "fighting"
    DARKNESS = "darkness"
    METAL = "metal"
    FAIRY = "fairy"
    DRAGON = "dragon"
    COLORLESS = "colorless"


class IdiomaCarta(StrEnum):
    """Idioma impreso en la carta. Distinto del idioma de UI del usuario.

    Los 8 idiomas que PSA acepta para grading; cubre los mercados objetivo
    + los mercados secundarios (JP/KR/ZH-T son fuertes en TCG).
    """

    EN = "EN"
    JP = "JP"
    ES = "ES"
    DE = "DE"
    FR = "FR"
    IT = "IT"
    KR = "KR"
    ZH_T = "ZH_T"
