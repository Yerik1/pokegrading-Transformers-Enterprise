"""Reglas de validación de dominio para el módulo de usuarios.

Estas reglas no dependen de FastAPI ni de SQLAlchemy: son funciones puras
sobre tipos primitivos. Esto las hace fácilmente testeables (cobertura
≥ 75% de la capa de dominio — S4).
"""

from __future__ import annotations

from pokegrading.compartido.errores import ErrorValidacion

# Longitud mínima de contraseña. La US dice "longitud mínima" sin fijar
# valor; 10 es el mínimo recomendado actual con los otros constraints.
LONGITUD_MINIMA_PASSWORD: int = 10

# Lista de dominios de correo descartables más comunes. En Sprint 2 esto
# se moverá a una tabla de configuración o a un archivo externo.
DOMINIOS_BLOQUEADOS: frozenset[str] = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "tempmail.com",
        "10minutemail.com",
        "throwawaymail.com",
        "yopmail.com",
        "trashmail.com",
        "fakeinbox.com",
        "dispostable.com",
        "getnada.com",
        "sharklasers.com",
    }
)


def validar_password(plano: str) -> None:
    """Valida que la contraseña cumpla los criterios de aceptación.

    Reglas (US Registrar Cuenta):
    - Longitud mínima `LONGITUD_MINIMA_PASSWORD`
    - Al menos una letra mayúscula
    - Al menos un dígito

    Args:
        plano: contraseña en texto plano.

    Raises:
        ErrorValidacion: si alguna regla no se cumple. El mensaje indica
            específicamente qué regla falló (criterio de mensajes
            específicos por campo).
    """
    if len(plano) < LONGITUD_MINIMA_PASSWORD:
        raise ErrorValidacion(
            codigo="password_muy_corta",
            mensaje=(
                f"La contraseña debe tener al menos {LONGITUD_MINIMA_PASSWORD} "
                f"caracteres."
            ),
            campo="contrasena",
        )
    if not any(c.isupper() for c in plano):
        raise ErrorValidacion(
            codigo="password_sin_mayuscula",
            mensaje="La contraseña debe contener al menos una letra mayúscula.",
            campo="contrasena",
        )
    if not any(c.isdigit() for c in plano):
        raise ErrorValidacion(
            codigo="password_sin_digito",
            mensaje="La contraseña debe contener al menos un dígito.",
            campo="contrasena",
        )


def validar_dominio_correo(correo: str) -> None:
    """Rechaza correos de dominios descartables o no autorizados.

    Args:
        correo: dirección de correo ya validada en formato.

    Raises:
        ErrorValidacion: si el dominio está en la blocklist.
    """
    dominio = correo.rsplit("@", 1)[-1].lower()
    if dominio in DOMINIOS_BLOQUEADOS:
        raise ErrorValidacion(
            codigo="dominio_bloqueado",
            mensaje=(
                "Este dominio de correo no está permitido. Por favor usa una "
                "dirección de correo personal o corporativa."
            ),
            campo="correo",
        )
