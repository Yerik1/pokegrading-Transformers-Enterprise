# PokéGrading

Plataforma de pre-grading de cartas Pokémon para LATAM. Segunda iniciativa de PokeVault.

> **Estado:** Sprint 1 — scaffold + US "Registrar cuenta" (Submitter).

## Stack

- **Backend:** Python 3.12 · FastAPI 0.111 · SQLAlchemy 2 (async) · Pydantic v2 · PostgreSQL 16 · Alembic
- **Frontend:** _Pendiente — se inicia en la siguiente iteración_
- **Infra local:** Docker Compose (Postgres)
- **Arquitectura:** Monolito modular con procesamiento async en background (ver `ADR-001` en el wiki)

## Estructura del repo

```text
pokegrading/
├── backend/
│   ├── src/pokegrading/
│   │   ├── compartido/        Cross-cutting: config, db, logging, errores, seguridad
│   │   ├── usuarios/          Módulo: cuentas y autenticación
│   │   ├── catalogo/          Módulo: catálogo de cartas (próximas US)
│   │   ├── grading/           Módulo: motor de scoring (futuro)
│   │   └── identificacion/    Módulo: identificación de cartas (futuro)
│   ├── alembic/               Migraciones de BD
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                  Pendiente
├── docker-compose.yml
└── .env.example
```

## Cómo correr el proyecto en local

Requisitos: **Docker** y **Python 3.12+**.

```bash
# 1. Copia el archivo de entorno y editalo si quieres
cp .env.example .env

# 2. Levanta PostgreSQL local
docker compose up -d db

# 3. Instala el backend en modo editable
cd backend
python -m venv .venv
source .venv/bin/activate   # o .venv\Scripts\activate en Windows
pip install -e ".[dev]"

# 4. Aplica las migraciones
alembic upgrade head

# 5. Levanta la API
uvicorn pokegrading.main:app --reload --host 0.0.0.0 --port 8000
```

API disponible en `http://localhost:8000`. Docs OpenAPI en `http://localhost:8000/docs`.

## Endpoints implementados en Sprint 1

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/usuarios/registro` | Registrar cuenta de Submitter |
| `GET`  | `/health` | Health check |

## Convenciones

Siguen lo definido en **V6: Proceso de Construcción** del wiki:

- Archivos/módulos en `snake_case`, clases en `PascalCase`, rutas API en `kebab-case`
- Formateo: `black` (line-length 88). Linter: `ruff`
- Type hints obligatorios en funciones públicas. Docstrings estilo Google
- Todo endpoint FastAPI es `async def`
- Commits: Conventional Commits (`feat:`, `fix:`, `refactor:`, etc.)
- Branches: `feature/US-XX-descripcion-corta` desde `develop`

## Errores frecuentes de setup (S1)

1. **`role "postgres" does not exist`** — corre `docker compose down -v` y vuelve a levantar.
2. **`could not translate host name "db"`** — estás corriendo el backend fuera de Docker; tu `DATABASE_URL` debe apuntar a `localhost`, no a `db`.
3. **`alembic: command not found`** — activa el venv (`source backend/.venv/bin/activate`).
4. **`No module named pokegrading`** — corre `pip install -e ".[dev]"` desde `backend/`.
5. **`asyncpg.exceptions.InvalidCatalogNameError`** — la BD `pokegrading_dev` aún no existe; espera 2-3s a que Postgres termine de arrancar.
