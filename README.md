# PokéGrading

Plataforma de pre-grading de cartas Pokémon para LATAM. El usuario sube una
foto de su carta y el sistema le devuelve una estimación de grado y una
recomendación de si vale la pena enviarla a una grading house profesional
(PSA, BGS, CGC).

Segunda iniciativa de PokéVault S.R.L., hermana de PokéMarket.

> **Disclosure:** PokéGrading produce estimaciones informativas. No es ni
> sustituye a las casas certificadoras profesionales.

---

## Estado de Sprint 1

| US | Estado | Notas |
|---|---|---|
| Registrar cuenta (Submitter) | ✅ Done | Frontend + backend, validaciones, disclosure |
| Iniciar sesión | ✅ Done | JWT con rotación de refresh tokens |
| Agregar carta al catálogo | ✅ Done | Admin/SuperAdmin only, imágenes en Azure Blob |
| Infraestructura compartida | ✅ Done | Auth, almacenamiento, errores, logging, CI |

Tech debt explícito para Sprint 2+:
- **US nueva:** "Validar carta del catálogo con doble verificación (R11)" — el wiki técnico exige validación dual; Sprint 1 la difiere por decisión de equipo (ver `docs/decisiones.md`).

---

## Stack

**Backend:** Python 3.12 · FastAPI 0.111+ · SQLAlchemy 2 async · PostgreSQL 16 · Alembic · Pydantic v2 · PyJWT · bcrypt · azure-storage-blob · Pillow · structlog

**Frontend:** TypeScript 5.4 · React 18 · Vite · Tailwind CSS 3 · Zustand · Axios · React Router 6

**Infra:** Docker Compose (dev local) · Azure Blob Storage · Azure Container Apps (prod) · GitHub Actions (CI)

**Calidad:** pytest + pytest-asyncio + pytest-cov · ruff · black · pre-commit · TypeScript strict mode

---

## Pre-requisitos

- **Python 3.12+** (recomendado: instalado desde python.org en Windows, no MSYS2)
- **Node.js 22+**
- **Docker Desktop** (para Postgres local)
- **Azure for Students** con un Storage Account creado (ver `docs/azure-setup.md`)
- **Git** (con tu identidad configurada)

---

## Quick start

```bash
# 1. Clonar
git clone https://github.com/Transformers-Enterprise/pokegrading.git
cd pokegrading-Transformers-Enterprise

# 2. Crear .env y completarlo
cp .env.example .env
# Editar .env: poner AZURE_STORAGE_CONNECTION_STRING con la real (ver docs/azure-setup.md)

# 3. Setup completo (venv + deps backend + deps frontend)
make setup

# 4. Levantar Postgres
make db-up
make migrate

# 5. Crear tu primer superadmin
make crear-admin ARGS="--correo root@pokegrading.com --alias root --rol superadmin"
# (te pide la contraseña interactivamente)

# 6. Verificar que todo conecta bien
make test           # ~45 tests deben pasar
make azure-check    # debe terminar con "Azure Blob Storage verificado correctamente"
```

Y para desarrollo diario, abre dos terminales:

```bash
# Terminal 1: backend
make dev

# Terminal 2: frontend
make frontend-dev
```

Frontend en http://localhost:5173, backend en http://localhost:8000, Swagger en http://localhost:8000/docs.

---

## Estructura del repo

```
pokegrading-Transformers-Enterprise/
├── backend/
│   ├── src/pokegrading/
│   │   ├── compartido/          # Auth, db, errores, logging, almacenamiento
│   │   ├── usuarios/            # Registro, login, refresh, dependencias
│   │   ├── catalogo/            # Cartas catálogo
│   │   ├── identificacion/      # (placeholder Sprint 2+)
│   │   └── grading/             # (placeholder Sprint 2+)
│   ├── alembic/versions/        # Migraciones
│   ├── scripts/                 # CLIs: crear_admin, verificar_azure
│   └── tests/
├── frontend/
│   └── src/
│       ├── compartido/          # Auth store, layout, errores, axios cliente
│       ├── usuarios/            # Registro, login, inicio
│       └── catalogo/            # Agregar carta admin
├── docs/
│   ├── azure-setup.md           # Paso a paso del setup de Azure
│   └── decisiones.md            # Log de decisiones del equipo
├── .github/workflows/ci.yml     # CI: backend + frontend
├── docker-compose.yml           # Postgres en dev
├── Makefile                     # Comandos del proyecto
└── README.md
```

---

## Arquitectura (resumen)

**Modular monolith** (ADR-001):

- Cada módulo de dominio (`usuarios`, `catalogo`, `grading`, `identificacion`) tiene su propia capa de `modelos` + `schemas` + `reglas` + `repositorio` + `servicio` + `router`.
- Lo transversal vive en `compartido/` (auth, db, errores, almacenamiento, logging).
- Las dependencias se inyectan vía FastAPI `Depends(...)` — esto permite que los tests overrideen sesión de BD y almacenamiento sin tocar el código de producción.

**Almacenamiento de imágenes:**
- Interfaz abstracta `IAlmacenamientoImagenes`.
- Implementación real `AlmacenamientoAzureBlob`.
- Implementación fake `AlmacenamientoEnMemoria` (solo tests).
- Permite swap de proveedor sin tocar el dominio.

**Autenticación:**
- JWT con HS256.
- Access token (15 min) + refresh token (7 días).
- Rotación de refresh tokens en cada `/auth/refresh` (defensa si el refresh se filtra).

---

## Comandos disponibles

```bash
make help                                       # lista todos
```

Los principales:

| Comando | Qué hace |
|---|---|
| `make setup` | Instala todo (venv + backend deps + frontend deps + env) |
| `make dev` | Levanta backend FastAPI con auto-reload |
| `make frontend-dev` | Levanta frontend Vite |
| `make test` | Corre tests del backend (~45 tests) |
| `make test-cov` | Tests con reporte de cobertura (umbral 75%) |
| `make lint` | ruff + black --check sobre el backend |
| `make format` | Aplica ruff --fix + black al backend |
| `make frontend-type-check` | TypeScript strict check |
| `make migrate` | Aplica migraciones pendientes |
| `make migration MSG="..."` | Crea una migración nueva |
| `make db-up` / `make db-down` | Levanta/apaga Postgres en Docker |
| `make db-shell` | Abre psql contra la BD dev |
| `make db-reset` | Wipea la BD y reaplica migraciones |
| `make crear-admin ARGS="..."` | Crea admin/superadmin vía CLI |
| `make azure-check` | Verifica conexión a Azure Blob |
| `make check` | lint backend + type-check frontend |
| `make clean` | Limpia caches |
| `make nuke` | Borra venv + node_modules + volumen DB |

---

## Convenciones del proyecto

Definidas en V6 §3.1 del wiki:

| Elemento | Convención | Ejemplo |
|---|---|---|
| Archivos / módulos Python | `snake_case` | `crear_carta_service.py` |
| Clases | `PascalCase` | `CrearCartaService` |
| Tablas / columnas BD | `snake_case` | `cartas_catalogo`, `created_at` |
| Rutas API | `kebab-case` | `/api/v1/catalogo/cartas` |
| Variables de entorno | `UPPER_SNAKE_CASE` | `AZURE_STORAGE_CONNECTION_STRING` |
| Claves de Key Vault | `kebab-case` | `azure-storage-connection-string` |
| Branches Git | `tipo/US-XX-descripcion` | `feature/US-43-agregar-carta-catalogo` |

**Decisiones de estilo:**
- Async-first (todos los endpoints son async)
- Tipos obligatorios (mypy strict no obligatorio aún, pero usar type hints)
- Docstrings estilo Google
- Mensajes de commit en español, código en inglés (excepto identifiers del dominio que están en español)
- Sin `except Exception` desnudo (V6 §4.1)

---

## Gobernabilidad

Toda la infra cloud sigue las convenciones del wiki **DG §7.5**:

- Resource Group dev: `rg-pokegrading-dev`
- Storage Account dev: `stpokegradingdev`
- Container blobs cartas: `cartas-referencia`
- Región: East US 2
- Tags obligatorios: `environment=dev`, `project=pokegrading`

Presupuesto dev: **$80/mes máx** (DO §7.2). El consumo real estimado para Sprint 1: <$5/mes.

---

## Documentación adicional

- **`docs/azure-setup.md`** — Paso a paso del setup de Azure Blob Storage
- **`docs/decisiones.md`** — Log de decisiones técnicas del equipo
- **Wiki técnico** — En Azure DevOps: requerimientos, drivers, ADRs, diseño detallado

---

## Equipo

| Rol | Notas |
|---|---|
| Equipo dev | 4 personas, roles rotativos (Scrum) |
| Empresa | PokéVault S.R.L. (Costa Rica / Panamá) |
| Curso | Diseño de Software (2026-I, TEC) |
| Milestone | 200 evaluaciones externas + NPS ≥ 40 antes del 31-dic-2026 |

---

## Flujo de trabajo

Git Flow simplificado:

```
main ←── develop ←── feature/US-XX-descripcion
```

- Los `feature/*` se crean desde `develop`.
- Los PRs van contra `develop`.
- `develop` → `main` solo en releases (final de sprint).
- `hotfix/*` salen de `main` y mergean a `main` y `develop`.

Reglas de PR:
- Todo PR pasa por CI (`.github/workflows/ci.yml`).
- Backend: lint (ruff+black) + tests (cov ≥75%).
- Frontend: type-check + build.
- Branch protection activa en `develop` y `main`.

---

## Soporte

Para reportar bugs, abrir un issue en GitHub o el board de Azure DevOps.
Para dudas urgentes del equipo, el canal de Slack del grupo.
