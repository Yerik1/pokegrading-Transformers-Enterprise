# =============================================================================
# PokéGrading — Makefile del proyecto
#
# Cubre los workflows de Sprint 1: backend (FastAPI + Postgres + Azure Blob)
# y frontend (Vite + React + Tailwind).
#
# Cross-platform: detecta Windows vs Unix y elige binarios apropiados.
# Las rutas se quotean para soportar espacios y tildes en directorios.
# =============================================================================

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

BACKEND_DIR := backend
FRONTEND_DIR := frontend
VENV_DIR := .venv

# Detectar OS para usar el Python correcto (.exe en Windows)
ifeq ($(OS),Windows_NT)
    PYTHON := $(abspath $(VENV_DIR)/Scripts/python.exe)
    NPM := npm.cmd
else
    PYTHON := $(abspath $(VENV_DIR)/bin/python)
    NPM := npm
endif

.DEFAULT_GOAL := help

# =============================================================================
# HELP
# =============================================================================

.PHONY: help
help:  ## Lista todos los targets disponibles
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# SETUP
# =============================================================================

.PHONY: setup env install frontend-install

setup: env install frontend-install  ## Setup completo: env + backend deps + frontend deps

env:  ## Crea .env desde .env.example si no existe
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ".env creado desde .env.example — editalo con tus valores reales"; \
	else \
		echo ".env ya existe"; \
	fi

install:  ## Crea venv (si no existe) e instala deps del backend en modo editable
	@python -m venv $(VENV_DIR) 2>/dev/null || true
	"$(PYTHON)" -m pip install --upgrade pip
	"$(PYTHON)" -m pip install -e "./$(BACKEND_DIR)[dev]"

frontend-install:  ## Instala dependencias del frontend
	cd $(FRONTEND_DIR) && $(NPM) install

# =============================================================================
# BACKEND - BD (Postgres en Docker)
# =============================================================================

.PHONY: db-up db-down db-reset db-shell wait-db

db-up:  ## Levanta Postgres en Docker
	docker compose up -d db

db-down:  ## Apaga Postgres
	docker compose stop db

db-reset:  ## Borra el volumen de Postgres y vuelve a aplicar migraciones (destructivo)
	docker compose down -v
	$(MAKE) db-up
	$(MAKE) wait-db
	$(MAKE) migrate

db-shell:  ## Abre psql contra la BD de dev
	docker compose exec db psql -U pokegrading -d pokegrading_dev

wait-db:  ## Espera hasta 10s a que Postgres esté listo
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		docker compose exec -T db pg_isready -U pokegrading >/dev/null 2>&1 && exit 0; \
		sleep 1; \
	done; \
	echo "ERROR: Postgres no respondió en 10s"; exit 1

# =============================================================================
# BACKEND - MIGRACIONES (Alembic)
# =============================================================================

.PHONY: migrate downgrade migration

migrate:  ## Aplica todas las migraciones pendientes
	cd $(BACKEND_DIR) && "$(PYTHON)" -m alembic upgrade head

downgrade:  ## Revierte la última migración
	cd $(BACKEND_DIR) && "$(PYTHON)" -m alembic downgrade -1

migration:  ## Crea migración nueva. Uso: make migration MSG="descripcion corta"
	@if [ -z "$(MSG)" ]; then \
		echo "ERROR: especificar MSG. Uso: make migration MSG='descripcion'"; \
		exit 1; \
	fi
	cd $(BACKEND_DIR) && "$(PYTHON)" -m alembic revision --autogenerate -m "$(MSG)"

# =============================================================================
# BACKEND - DEV / TEST / LINT
# =============================================================================

.PHONY: dev test test-cov lint format

dev:  ## Levanta backend FastAPI con auto-reload en localhost:8000
	cd $(BACKEND_DIR) && "$(PYTHON)" -m uvicorn pokegrading.main:app --reload --port 8000

test:  ## Corre todos los tests del backend
	cd $(BACKEND_DIR) && "$(PYTHON)" -m pytest

test-cov:  ## Tests con reporte de cobertura (HTML en backend/htmlcov, umbral 75%)
	cd $(BACKEND_DIR) && "$(PYTHON)" -m pytest \
		--cov=src/pokegrading \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=xml \
		--cov-fail-under=75

lint:  ## Verifica formato y estilo del backend (sin modificar archivos)
	cd $(BACKEND_DIR) && "$(PYTHON)" -m ruff check src tests
	cd $(BACKEND_DIR) && "$(PYTHON)" -m black --check src tests

format:  ## Aplica formato y arregla fixes de lint en el backend
	cd $(BACKEND_DIR) && "$(PYTHON)" -m ruff check --fix src tests
	cd $(BACKEND_DIR) && "$(PYTHON)" -m black src tests

# =============================================================================
# BACKEND - SCRIPTS / CLI
# =============================================================================

.PHONY: crear-admin azure-check b2b-cuenta

crear-admin:  ## Crea un usuario admin/superadmin. Uso: make crear-admin ARGS="--correo X --alias Y --rol superadmin"
	cd $(BACKEND_DIR) && "$(PYTHON)" -m scripts.crear_admin $(ARGS)

azure-check:  ## Verifica que la conexión a Azure Blob Storage funciona
	cd $(BACKEND_DIR) && "$(PYTHON)" -m scripts.verificar_azure

b2b-cuenta:  ## Crea cuenta B2B con API key. Uso: make b2b-cuenta ARGS="--tienda 'Nombre' --correo x@ejemplo.com"
	cd $(BACKEND_DIR) && "$(PYTHON)" -m scripts.crear_cuenta_b2b $(ARGS)

# =============================================================================
# FRONTEND
# =============================================================================

.PHONY: frontend-dev frontend-build frontend-type-check

frontend-dev:  ## Levanta frontend Vite en localhost:5173
	cd $(FRONTEND_DIR) && $(NPM) run dev

frontend-build:  ## Build de producción del frontend
	cd $(FRONTEND_DIR) && $(NPM) run build

frontend-type-check:  ## Verifica tipos de TypeScript (strict mode)
	cd $(FRONTEND_DIR) && $(NPM) run type-check

# =============================================================================
# QA / CHECK GLOBAL
# =============================================================================

.PHONY: check check-all

check: lint frontend-type-check  ## Lint backend + type-check frontend (rápido, sin tests)

check-all: lint test frontend-type-check frontend-build  ## Suite completa: lint + tests + frontend build

# =============================================================================
# DOCKER (full stack opcional)
# =============================================================================

.PHONY: docker-build docker-up docker-down logs

docker-build:  ## Construye las imágenes Docker del stack completo
	docker compose build

docker-up:  ## Levanta todos los servicios con Docker
	docker compose up -d

docker-down:  ## Apaga todos los servicios Docker
	docker compose down

logs:  ## Tail de los logs de Docker
	docker compose logs -f

# =============================================================================
# LIMPIEZA
# =============================================================================

.PHONY: clean nuke

clean:  ## Limpia caches de Python, pytest, ruff y dist del frontend
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	@rm -rf $(BACKEND_DIR)/htmlcov $(BACKEND_DIR)/.coverage $(BACKEND_DIR)/coverage.xml
	@rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/node_modules/.cache
	@echo "Limpieza completa."

nuke: clean  ## clean + borra venv + node_modules + volumen Docker (todo destructivo)
	docker compose down -v 2>/dev/null || true
	rm -rf $(VENV_DIR)
	rm -rf $(FRONTEND_DIR)/node_modules
	@echo "Repo limpio. Corré 'make setup' para volver a empezar."