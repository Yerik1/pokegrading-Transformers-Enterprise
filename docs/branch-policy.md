# Política de Branches

## `main`

Reglas:

- No permite push directo.
- Requiere Pull Request.
- Requiere al menos 1 aprobación.
- Requiere conversaciones resueltas.
- No permite force push.
- No permite eliminación.
- Se usa únicamente para releases.

## `develop`

Reglas:

- No permite push directo.
- Requiere Pull Request.
- Requiere al menos 1 aprobación.
- Requiere conversaciones resueltas.
- No permite force push.
- No permite eliminación.
- Es la rama base para features, fixes, docs y chores.

## Status checks

Los status checks obligatorios quedan pendientes de activación hasta que exista un pipeline de CI ejecutado al menos una vez. GitHub requiere checks existentes para poder hacerlos obligatorios.

## Merge strategy

La estrategia oficial es:

```text
Squash and Merge