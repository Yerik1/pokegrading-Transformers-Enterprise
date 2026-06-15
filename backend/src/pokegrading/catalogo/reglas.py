"""Reglas de validación de imágenes de catálogo (SP3, DA-12).

Validaciones implementadas:
1. **Tamaño:** ≤ 10 MB (SP3)
2. **Formato real por magic bytes:** rechaza polyglot files (DA-12).
   Solo se aceptan JPEG y PNG. HEIC se rechaza explícitamente.
3. **Decodificación:** Pillow debe poder abrir la imagen (rechaza corrupción).
4. **Dimensiones:** 600×840 mín, 4000×6000 máx.

NUNCA se confía en el `Content-Type` que envía el cliente — se inspecciona
el contenido real.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, UnidentifiedImageError

from pokegrading.compartido.errores import ErrorValidacion

# === Constantes (parametrizadas según política del proyecto) ===

TAMANO_MAXIMO_BYTES: int = 10 * 1024 * 1024  # 10 MB (SP3)

ANCHO_MINIMO: int = 600
ALTO_MINIMO: int = 840
ANCHO_MAXIMO: int = 4000
ALTO_MAXIMO: int = 6000

MIME_JPEG = "image/jpeg"
MIME_PNG = "image/png"
MIME_HEIC = "image/heic"

MIMES_PERMITIDOS: frozenset[str] = frozenset({MIME_JPEG, MIME_PNG})

# Magic bytes — los primeros bytes que identifican el formato real
MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_PNG = b"\x89PNG\r\n\x1a\n"

# HEIC: ISO Base Media Format. La caja "ftyp" está en offset 4 y el brand
# (4 bytes que indican variante: heic, heix, mif1...) está en offset 8.
HEIC_FTYP_BRANDS: frozenset[bytes] = frozenset(
    {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heim", b"heis"}
)


def _detectar_formato_real(contenido: bytes) -> str:
    """Detecta el formato real mirando magic bytes.

    Returns:
        El MIME type detectado, o `"unknown"` si no se reconoce.
    """
    if contenido.startswith(MAGIC_JPEG):
        return MIME_JPEG
    if contenido.startswith(MAGIC_PNG):
        return MIME_PNG
    if len(contenido) >= 12 and contenido[4:8] == b"ftyp":
        brand = contenido[8:12]
        if brand in HEIC_FTYP_BRANDS:
            return MIME_HEIC
    return "unknown"


def validar_imagen(
    contenido: bytes,
    *,
    content_type_cliente: str,
    campo: str,
) -> str:
    """Valida una imagen contra los criterios de SP3 y DA-12.

    Args:
        contenido: bytes crudos de la imagen recibida.
        content_type_cliente: lo que envió el navegador (solo para logs;
            la decisión real se basa en magic bytes).
        campo: nombre del campo del form (para mensajes de error específicos).

    Returns:
        MIME type real detectado (ej. `"image/jpeg"`).

    Raises:
        ErrorValidacion: si alguna regla no se cumple.
    """
    # 1. Tamaño
    if len(contenido) == 0:
        raise ErrorValidacion(
            codigo="imagen_vacia",
            mensaje="El archivo de imagen está vacío.",
            campo=campo,
        )
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise ErrorValidacion(
            codigo="imagen_demasiado_grande",
            mensaje=(
                f"La imagen excede el tamaño máximo de "
                f"{TAMANO_MAXIMO_BYTES // (1024 * 1024)} MB."
            ),
            campo=campo,
        )

    # 2. Detección por magic bytes (no por content_type del cliente)
    formato_real = _detectar_formato_real(contenido)

    if formato_real == MIME_HEIC:
        raise ErrorValidacion(
            codigo="formato_heic_no_soportado",
            mensaje=(
                "El formato HEIC no es soportado para imágenes de catálogo. "
                "Convertí la imagen a JPEG o PNG antes de subirla."
            ),
            campo=campo,
        )

    if formato_real not in MIMES_PERMITIDOS:
        raise ErrorValidacion(
            codigo="formato_no_soportado",
            mensaje="Formato no soportado. Solo se aceptan JPEG y PNG.",
            campo=campo,
        )

    # 3. Decodificación con Pillow (detecta corrupción / polyglot)
    try:
        Image.open(BytesIO(contenido)).verify()
        # verify() invalida la imagen; reabrir para leer dimensiones
        img = Image.open(BytesIO(contenido))
        ancho, alto = img.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ErrorValidacion(
            codigo="imagen_corrupta",
            mensaje=(
                "La imagen no se pudo decodificar correctamente "
                "(archivo corrupto o malformado)."
            ),
            campo=campo,
        ) from exc

    # 4. Dimensiones dentro de los límites
    if ancho < ANCHO_MINIMO or alto < ALTO_MINIMO:
        raise ErrorValidacion(
            codigo="imagen_resolucion_insuficiente",
            mensaje=(
                f"Resolución mínima requerida: {ANCHO_MINIMO}×{ALTO_MINIMO} px. "
                f"Imagen recibida: {ancho}×{alto} px."
            ),
            campo=campo,
        )
    if ancho > ANCHO_MAXIMO or alto > ALTO_MAXIMO:
        raise ErrorValidacion(
            codigo="imagen_resolucion_excesiva",
            mensaje=(
                f"Resolución máxima permitida: {ANCHO_MAXIMO}×{ALTO_MAXIMO} px. "
                f"Imagen recibida: {ancho}×{alto} px."
            ),
            campo=campo,
        )

    return formato_real
