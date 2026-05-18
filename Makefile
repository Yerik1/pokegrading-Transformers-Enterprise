# =============================================================================
# PokéGrading — Makefile
#
# Comandos estandarizados para setup, desarrollo y operación del proyecto.
# Funciona en Windows (cmd, PowerShell, Git Bash, MSYS2), macOS y Linux.
#
# Uso:
#   make            -> muestra la lista de targets
#   make setup      -> setup completo desde cero (venv + deps + db + migrate)
#   make dev        -> levanta la API con hot reload
#   make test       -> corre la suite de tests
#   make check      -> lint + test (lo que valida CI antes de merge)
#
# Convención: targets con `##` aparecen en `make help`.
# =============================================================================

# ----------------------------------------------------------------------------
# Detección de OS y rutas portables
# ----------------------------------------------------------------------------
ifeq ($(OS),Windows_NT)
    VENV_BIN          := .venv/Scripts
    EXE               := .exe
    PYTHON_BOOTSTRAP  := py -3.12
else
    VENV_BIN          := .venv/bin
    EXE               :=
    PYTHON_BOOTSTRAP  := python3.12
endif

# Binarios del venv como rutas absolutas (sobreviven cambios de cwd)
PYTHON  := "$(abspath $(VENV_BIN)/python$(EXE))"
PIP     := "$(abspath $(VENV_BIN)/pip$(EXE))"
ALEMBIC := $(PYTHON) -m alembic
UVICORN := $(PYTHON) -m uvicorn
PYTEST  := $(PYTHON) -m pytest
BLACK   := $(PYTHON) -m black
RUFF    := $(PYTHON) -m ruff

DOCKER_COMPOSE := docker compose
BACKEND_DIR    := backend
# npm en Windows es un shim .cmd; bash no lo encuentra sin la extension explicita
ifeq ($(OS),Windows_NT)
    NPM := npm.cmd
else
    NPM := npm
endif
.DEFAULT_GOAL := help

# Para targets que hacen operaciones de filesystem, usamos Python en vez de
# `cmd` o `sh` para que sea agnóstico al shell que use make (algunos entornos
# Windows como Git Bash/MSYS2 usan sh aunque $(OS)=Windows_NT).
#
# Para evitar problemas con saltos de línea entre cmd y sh, los scripts de
# Python se mantienen en UNA SOLA LÍNEA. Verboso pero portable.

# ============================================================================
# Help (auto-generado desde los comentarios `##`)
# ============================================================================
.PHONY: help
help:  ## Muestra esta ayuda
	@$(PYTHON_BOOTSTRAP) -c "import re; lines = open('Makefile', encoding='utf-8').read().splitlines(); print('PokeGrading - Targets disponibles:'); print(''); [print(f'  {m.group(1):<18} {m.group(2)}') for l in lines for m in [re.match(r'^([a-zA-Z][a-zA-Z0-9_-]+):.*?##\s*(.*)$$', l)] if m]"

# ============================================================================
# SETUP
# ============================================================================

.venv:
	$(PYTHON_BOOTSTRAP) -m venv .venv
	$(PIP) install --upgrade pip

.PHONY: venv
venv: .venv  ## Crea la virtualenv .venv con Python 3.12

.PHONY: install
install: .venv  ## Instala el backend en modo editable + deps de desarrollo
	$(PIP) install -e "./$(BACKEND_DIR)[dev]"

.PHONY: env
env:  ## Crea .env desde .env.example si todavia no existe
	@$(PYTHON_BOOTSTRAP) -c "import shutil, pathlib; p = pathlib.Path('.env'); shutil.copy('.env.example', p) if not p.exists() else None; print('.env listo')"

.PHONY: setup
setup: venv install env db-up wait-db migrate frontend-install frontend-env  ## Setup completo desde cero (backend + frontend)
	@$(PYTHON_BOOTSTRAP) -c "print(''); print('Setup listo. Levantar:'); print('  Backend:  make dev'); print('  Frontend: make frontend-dev')"

# ============================================================================
# BASE DE DATOS
# ============================================================================

.PHONY: db-up
db-up:  ## Levanta PostgreSQL en Docker (background)
	$(DOCKER_COMPOSE) up -d db

.PHONY: db-down
db-down:  ## Detiene PostgreSQL sin borrar datos
	$(DOCKER_COMPOSE) stop db

.PHONY: db-reset
db-reset:  ## DESTRUYE el volumen de Postgres y vuelve a migrarlo limpio
	$(DOCKER_COMPOSE) down -v
	$(DOCKER_COMPOSE) up -d db
	@$(MAKE) wait-db
	@$(MAKE) migrate

.PHONY: db-shell
db-shell:  ## Abre psql contra la BD local
	docker exec -it pokegrading-db psql -U pokegrading -d pokegrading_dev

.PHONY: wait-db
wait-db:  ## Espera a que Postgres este healthy (max 30s)
	@$(PYTHON_BOOTSTRAP) -c "import subprocess,time,sys; r=subprocess.run; [sys.exit(0) if r(['docker','exec','pokegrading-db','pg_isready','-U','pokegrading'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0 and not print('Postgres listo.') else (print('Esperando Postgres... ({}/30)'.format(i+1)), time.sleep(1)) for i in range(30)]; print('Postgres no respondio en 30s'); sys.exit(1)"

.PHONY: migrate
migrate:  ## Aplica todas las migraciones pendientes
	cd $(BACKEND_DIR) && $(ALEMBIC) upgrade head

.PHONY: downgrade
downgrade:  ## Revierte la ultima migracion
	cd $(BACKEND_DIR) && $(ALEMBIC) downgrade -1

.PHONY: migration
migration:  ## Crea una migracion nueva. Uso: make migration MSG="descripcion"
ifndef MSG
	@$(PYTHON_BOOTSTRAP) -c "import sys; print('Error: MSG es requerido. Uso: make migration MSG=\"agregar tabla cartas\"'); sys.exit(1)"
endif
	cd $(BACKEND_DIR) && $(ALEMBIC) revision --autogenerate -m "$(MSG)"

# ============================================================================
# DESARROLLO
# ============================================================================

.PHONY: dev
dev:  ## Levanta la API con hot reload (uvicorn)
	cd $(BACKEND_DIR) && $(UVICORN) pokegrading.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: test
test:  ## Corre la suite de tests
	cd $(BACKEND_DIR) && $(PYTEST)

.PHONY: test-cov
test-cov:  ## Corre los tests con reporte de cobertura
	cd $(BACKEND_DIR) && $(PYTEST) --cov=pokegrading --cov-report=term-missing --cov-report=html

.PHONY: lint
lint:  ## Detecta problemas con ruff
	$(RUFF) check $(BACKEND_DIR)/src $(BACKEND_DIR)/tests

.PHONY: format
format:  ## Formatea con black y arregla imports con ruff
	$(BLACK) $(BACKEND_DIR)/src $(BACKEND_DIR)/tests
	$(RUFF) check --fix $(BACKEND_DIR)/src $(BACKEND_DIR)/tests

.PHONY: check
check: lint test  ## Lo que valida CI: lint + test
	@$(PYTHON_BOOTSTRAP) -c "print('Check OK.')"

# ============================================================================
# DOCKER (stack completo, opcional)
# ============================================================================

.PHONY: docker-build
docker-build:  ## Build de la imagen del backend
	$(DOCKER_COMPOSE) --profile full build api

.PHONY: docker-up
docker-up:  ## Levanta API + DB en Docker (sin hot reload)
	$(DOCKER_COMPOSE) --profile full up -d

.PHONY: docker-down
docker-down:  ## Detiene el stack completo (sin borrar datos)
	$(DOCKER_COMPOSE) --profile full down

.PHONY: logs
logs:  ## Tail de logs del API en Docker
	$(DOCKER_COMPOSE) logs -f api

# ============================================================================
# FRONTEND
# ============================================================================

FRONTEND_DIR := frontend


.PHONY: frontend-install
frontend-install:  ## Instala dependencias del frontend (npm install)
	cd $(FRONTEND_DIR) && $(NPM) install
.PHONY: frontend-env
frontend-env:  ## Crea frontend/.env desde .env.example si no existe
	@$(PYTHON_BOOTSTRAP) -c "import shutil, pathlib; p = pathlib.Path('$(FRONTEND_DIR)/.env'); shutil.copy('$(FRONTEND_DIR)/.env.example', p) if not p.exists() else None; print('frontend/.env listo')"

.PHONY: frontend-dev
frontend-dev:  ## Levanta el frontend en modo dev (Vite, puerto 5173)
	cd $(FRONTEND_DIR) && $(NPM) run dev

.PHONY: frontend-build
frontend-build:  ## Compila el frontend para produccion
	cd $(FRONTEND_DIR) && $(NPM) run build

.PHONY: frontend-type-check
frontend-type-check:  ## Verifica tipos sin compilar
	cd $(FRONTEND_DIR) && $(NPM) run type-check

# ============================================================================
# CLI ADMINISTRATIVO
# ============================================================================

.PHONY: crear-admin
crear-admin:  ## Crea un usuario admin/superadmin. Uso: make crear-admin
	cd $(BACKEND_DIR) && $(PYTHON) -m scripts.crear_admin $(ARGS)

.PHONY: azure-check
azure-check:  ## Verifica que la conexion a Azure Blob Storage funciona
	cd $(BACKEND_DIR) && $(PYTHON) -m scripts.verificar_azure

# ============================================================================
# LIMPIEZA
# ============================================================================

.PHONY: clean
clean:  ## Borra caches de Python y reportes de tests
	@$(PYTHON_BOOTSTRAP) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; [shutil.rmtree(d, ignore_errors=True) for d in ['.pytest_cache', '.ruff_cache', 'htmlcov', '.mypy_cache']]; pathlib.Path('.coverage').unlink(missing_ok=True); print('Caches limpiadas.')"

.PHONY: nuke
nuke: clean  ## TODO: borra venv + volumen docker + caches. Reconstruye con make setup.
	-$(DOCKER_COMPOSE) down -v
	@$(PYTHON_BOOTSTRAP) -c "import shutil; shutil.rmtree('.venv', ignore_errors=True); print('venv y volumen destruidos. Reconstruye con: make setup')"