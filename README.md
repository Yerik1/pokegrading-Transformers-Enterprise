# PokéGrading

PokéGrading es una plataforma de pre-grading asistido para cartas Pokémon. El sistema permite estimar el grado probable de una carta, gestionar un catálogo de referencia, mantener trazabilidad de evaluaciones y preparar la integración futura con servicios externos como PokéMarket.

## Estado del proyecto

Sprint 1 — Configuración inicial, arquitectura base y primeras funcionalidades.

Funcionalidades objetivo del Sprint 1:

- Registrar cuenta.
- Agregar carta al catálogo.

## Stack definido

- Frontend: React.
- Backend: FastAPI.
- Base de datos: PostgreSQL / Azure Database for PostgreSQL.
- Almacenamiento de imágenes: Azure Blob Storage.
- Control de versiones: GitHub.
- Gestión del backlog y wiki: Azure DevOps.

## Estrategia de ramas

El proyecto usa un flujo basado en `main` y `develop`.

- `main`: rama estable para releases.
- `develop`: rama de integración del sprint.
- `feature/*`: nuevas funcionalidades.
- `fix/*`: correcciones.
- `docs/*`: documentación.
- `chore/*`: configuración y mantenimiento.
- `hotfix/*`: correcciones urgentes desde `main`.

Todo cambio debe entrar mediante Pull Request.

## Sprint 1

Las ramas principales esperadas para el Sprint 1 son:

- `chore/configuracion-inicial-proyecto`
- `feature/US-01-registrar-cuenta`
- `feature/US-02-agregar-carta-catalogo`
- `docs/evidencia-sprint1`

## Reglas generales

- No se permite hacer push directo a `main` ni `develop`.
- Todo Pull Request requiere al menos una aprobación.
- Los cambios deben estar vinculados al backlog de Azure DevOps.
- No se deben subir secretos, archivos `.env`, tokens ni credenciales.
- El merge se realiza mediante Squash and Merge.
- Los commits deben seguir Conventional Commits.

## Documentación

La documentación oficial del proyecto se mantiene en Azure DevOps Wiki. Este repositorio conserva documentación técnica de apoyo, estrategia de control de código, prompts de IA, diagramas exportados y archivos base del proyecto.