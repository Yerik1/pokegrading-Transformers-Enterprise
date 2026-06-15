"""Tipos y enums del dominio de usuarios."""

from __future__ import annotations

from enum import StrEnum


class Rol(StrEnum):
    """Roles del sistema (SP1).

    Jerarquía administrativa:
    - ADMIN: gestiona catálogo y usuarios.
    - SUPERADMIN: todo lo de ADMIN + gestión de admins y configuración del sistema.

    El registro público (`POST /api/v1/usuarios/registro`) solo crea SUBMITTER.
    Los roles administrativos se crean por CLI (`scripts/crear_admin.py`).
    """

    SUBMITTER = "submitter"
    REVIEWER = "reviewer"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"
    B2B_SERVICE_ACCOUNT = "b2b_service_account"


class Idioma(StrEnum):
    """Idiomas soportados por la plataforma."""

    ES = "es"
    EN = "en"


class Pais(StrEnum):
    """Países de mercados atendidos (referencia inicial de la US Registrar Cuenta).

    Códigos ISO 3166-1 alpha-2.
    """

    CR = "CR"  # Costa Rica
    PA = "PA"  # Panamá
    MX = "MX"  # México
    CO = "CO"  # Colombia
    CL = "CL"  # Chile
    AR = "AR"  # Argentina
