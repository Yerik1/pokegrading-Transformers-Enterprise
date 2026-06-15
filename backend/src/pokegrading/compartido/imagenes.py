from __future__ import annotations
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from pokegrading.compartido.errores import ErrorValidacion

TAMANO_MAXIMO_BYTES: int = 10 * 1024 * 1024
ANCHO_MINIMO: int = 600
ALTO_MINIMO: int = 840
ANCHO_MAXIMO: int = 4000
ALTO_MAXIMO: int = 6000
MIME_JPEG = "image/jpeg"
MIME_PNG = "image/png"
MIME_HEIC = "image/heic"
MIMES_PERMITIDOS: frozenset[str] = frozenset({MIME_JPEG, MIME_PNG})
MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
HEIC_FTYP_BRANDS: frozenset[bytes] = frozenset(
    {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heim", b"heis"}
)

def _detectar_formato_real(contenido: bytes) -> str:
    if contenido.startswith(MAGIC_JPEG):
        return MIME_JPEG
    if contenido.startswith(MAGIC_PNG):
        return MIME_PNG
    if len(contenido) >= 12 and contenido[4:8] == b"ftyp":
        brand = contenido[8:12]
        if brand in HEIC_FTYP_BRANDS:
            return MIME_HEIC
    return "unknown"

def validar_imagen(contenido: bytes, *, content_type_cliente: str, campo: str) -> str:
    """Valida una imagen de carta. Punto de entrada unico para todo el sistema."""
    if len(contenido) == 0:
        raise ErrorValidacion(codigo="imagen_vacia", mensaje="El archivo de imagen esta vacio.", campo=campo)
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise ErrorValidacion(codigo="imagen_demasiado_grande", mensaje=f"La imagen excede el tamano maximo de {TAMANO_MAXIMO_BYTES // (1024 * 1024)} MB.", campo=campo)
    formato_real = _detectar_formato_real(contenido)
    if formato_real == MIME_HEIC:
        raise ErrorValidacion(codigo="formato_heic_no_soportado", mensaje="El formato HEIC no esta soportado. Converti la imagen a JPEG o PNG.", campo=campo)
    if formato_real not in MIMES_PERMITIDOS:
        raise ErrorValidacion(codigo="formato_no_soportado", mensaje="Formato no soportado. Solo se aceptan JPEG y PNG.", campo=campo)
    try:
        Image.open(BytesIO(contenido)).verify()
        img = Image.open(BytesIO(contenido))
        ancho, alto = img.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ErrorValidacion(codigo="imagen_corrupta", mensaje="La imagen no se pudo decodificar correctamente.", campo=campo) from exc
    if ancho < ANCHO_MINIMO or alto < ALTO_MINIMO:
        raise ErrorValidacion(codigo="imagen_resolucion_insuficiente", mensaje=f"Resolucion minima requerida: {ANCHO_MINIMO}x{ALTO_MINIMO} px. Imagen recibida: {ancho}x{alto} px.", campo=campo)
    if ancho > ANCHO_MAXIMO or alto > ALTO_MAXIMO:
        raise ErrorValidacion(codigo="imagen_resolucion_excesiva", mensaje=f"Resolucion maxima permitida: {ANCHO_MAXIMO}x{ALTO_MAXIMO} px. Imagen recibida: {ancho}x{alto} px.", campo=campo)
    return formato_real
