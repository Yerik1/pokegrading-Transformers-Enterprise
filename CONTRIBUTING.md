# Guía de Contribución — PokéGrading

## Flujo de trabajo

1. Tomar una tarea o User Story desde Azure DevOps.
2. Crear una rama desde `develop`.
3. Hacer commits pequeños y descriptivos.
4. Abrir Pull Request hacia `develop`.
5. Solicitar revisión de al menos un compañero.
6. Resolver comentarios.
7. Hacer merge mediante Squash and Merge.
8. Eliminar la rama después del merge.

## Ramas

Formato recomendado:

- `feature/US-XX-descripcion-corta`
- `fix/BUG-XX-descripcion-corta`
- `docs/descripcion-corta`
- `chore/descripcion-corta`
- `hotfix/x.y.z-descripcion-corta`

Ejemplos:

- `feature/US-01-registrar-cuenta`
- `feature/US-02-agregar-carta-catalogo`
- `docs/actualizar-diagramas-sprint1`
- `chore/configuracion-inicial-proyecto`

## Commits

Se utiliza Conventional Commits.

Formato:

```text
tipo(scope): descripcion breve