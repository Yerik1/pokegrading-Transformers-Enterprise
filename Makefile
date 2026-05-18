# =============================================================================
# PokéGrading — Makefile
#
# Comandos estandarizados para setup, desarrollo y operación del proyecto.
# Funciona en Windows (con make instalado), macOS y Linux.
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
    RM_RF             := rd /s /q
    NULL              := nul
else
    VENV_BIN          := .venv/bin
    EXE               :=
    PYTHON_BOOTSTRAP  := python3.12
    RM_RF             := rm -rf
    NULL              := /dev/null
endif

# Binarios del venv como rutas absolutas para sobrevivir cambios de cwd
PYTHON  := $(abspath $(VENV_BIN)/python$(EXE))
PIP     := $(abspath $(VENV_BIN)/pip$(EXE))
ALEMBIC := $(PYTHON) -m alembic
UVICORN := $(PYTHON) -m uvicorn
PYTEST  := $(PYTHON) -m pytest
BLACK   := $(PYTHON) -m black
RUFF    := $(PYTHON) -m ruff

DOCKER_COMPOSE := docker compose
BACKEND_DIR    := backend

.DEFAULT_GOAL := help

# ----------------------------------------------------------------------------
# Help (auto-generado desde los comentarios `##`)
# ----------------------------------------------------------------------------
.PHONY: help
help:  ## Muestra esta ayuda
	@echo PokeGrading - Targets disponibles:
	@echo.
	@$(PYTHON_BOOTSTRAP) -c "import re,sys; \
	lines=open('Makefile',encoding='utf-8').read().splitlines(); \
	[print(f'  {m.group(1):<18} {m.group(2)}') for l in lines \
	 for m in [re.match(r'^([a-zA-Z][a-zA-Z0-9_-]+):.*?##\s*(.*)$$', l)] if m]"

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
ifeq ($(OS),Windows_NT)
	@if not exist .env (copy .env.example .env > $(NULL))
	@if not exist .env (echo No se pudo crear .env. & exit 1)
	@echo .env listo.
else
	@test -f .env || cp .env.example .env
	@echo ".env listo."
endif

.PHONY: setup
setup: venv install env db-up wait-db migrate  ## Setup completo desde cero
	@echo.
	@echo Setup listo. Para arrancar la API:
	@echo   make dev

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
wait-db:  ## Espera a que Postgres este healthy
	@$(PYTHON_BOOTSTRAP) -c "import time, subprocess; \
	[time.sleep(1) or (print('Esperando Postgres...') if i%3==0 else None) \
	 for i in range(30) \
	 if subprocess.run(['docker','exec','pokegrading-db','pg_isready','-U','pokegrading'], \
	   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0] \
	and print('Postgres listo.') or print('Postgres listo.')"

.PHONY: migrate
migrate:  ## Aplica todas las migraciones pendientes
	cd $(BACKEND_DIR) && $(ALEMBIC) upgrade head

.PHONY: downgrade
downgrade:  ## Revierte la ultima migracion
	cd $(BACKEND_DIR) && $(ALEMBIC) downgrade -1

.PHONY: migration
migration:  ## Crea una migracion nueva. Uso: make migration MSG="descripcion"
ifndef MSG
	@echo Error: MSG es requerido.
	@echo Uso: make migration MSG="agregar tabla cartas"
	@exit 1
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
	@echo Check OK.

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
# LIMPIEZA
# ============================================================================

.PHONY: clean
clean:  ## Borra caches de Python y reportes de tests
ifeq ($(OS),Windows_NT)
	@for /d /r . %%d in (__pycache__) do @if exist "%%d" $(RM_RF) "%%d" 2> $(NULL)
	@if exist .pytest_cache $(RM_RF) .pytest_cache
	@if exist .ruff_cache $(RM_RF) .ruff_cache
	@if exist htmlcov $(RM_RF) htmlcov
	@if exist .coverage del .coverage
else
	@find . -type d -name __pycache__ -exec $(RM_RF) {} + 2> $(NULL) || true
	@$(RM_RF) .pytest_cache .ruff_cache htmlcov .coverage
endif
	@echo Caches limpiadas.

.PHONY: nuke
nuke: clean  ## TODO: borra venv + volumen de docker + caches. Reconstruye con `make setup`.
	-$(DOCKER_COMPOSE) down -v
ifeq ($(OS),Windows_NT)
	@if exist .venv $(RM_RF) .venv
else
	@$(RM_RF) .venv
endif
	@echo Todo destruido. Reconstruye con: make setup