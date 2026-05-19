# Estrategia de Control de Código

PokéGrading utiliza GitHub para el control de versiones y Azure DevOps para la gestión del backlog, sprints y wiki.

## Ramas principales

| Rama | Propósito |
|---|---|
| `main` | Rama estable. Solo contiene versiones listas para release. |
| `develop` | Rama de integración del sprint. Todas las features se integran aquí antes de pasar a `main`. |

## Ramas de trabajo

| Tipo | Formato | Uso |
|---|---|---|
| Feature | `feature/US-XX-descripcion` | Nuevas funcionalidades asociadas a User Stories. |
| Fix | `fix/BUG-XX-descripcion` | Corrección de defectos. |
| Docs | `docs/descripcion` | Cambios de documentación. |
| Chore | `chore/descripcion` | Configuración, mantenimiento o tareas no funcionales. |
| Hotfix | `hotfix/x.y.z-descripcion` | Corrección urgente desde `main`. |

## Flujo general

1. Crear rama desde `develop`.
2. Desarrollar cambios.
3. Hacer commits siguiendo Conventional Commits.
4. Abrir Pull Request hacia `develop`.
5. Obtener al menos una aprobación.
6. Resolver conversaciones.
7. Hacer Squash and Merge.
8. Eliminar rama.

## Releases

Al final del sprint, `develop` se integra a `main` mediante Pull Request de release.

Formato de tag recomendado:

```text
v0.1.0-sprint1