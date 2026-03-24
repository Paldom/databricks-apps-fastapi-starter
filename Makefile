SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

UV ?= uv
NPM ?= npm
DOCKER_COMPOSE ?= docker compose

BACKEND_DIR ?= backend
FRONTEND_DIR ?= frontend

TARGET ?= dev
RESOURCE ?= fastapi_app
MIGRATION_MESSAGE ?= new migration

.PHONY: help \
	install install-backend install-frontend \
	dev-db dev-db-down migrate-up migrate-new \
	dev-api dev-frontend dev \
	requirements-export openapi-export frontend-api-gen generate \
	format lint typecheck security test frontend-build check load-test \
	bundle-validate bundle-deploy bundle-run bundle-summary

help:
	@echo "Common targets:"
	@echo "  make install"
	@echo "  make dev-db"
	@echo "  make migrate-up"
	@echo "  make dev"
	@echo "  make generate"
	@echo "  make check"
	@echo "  make bundle-validate TARGET=dev"
	@echo "  make bundle-deploy TARGET=staging"
	@echo "  make bundle-run TARGET=prod RESOURCE=fastapi_app"
	@echo "  make bundle-summary TARGET=dev"

# ── Install ────────────────────────────────────────────────────────

install: install-backend install-frontend

install-backend:
	cd $(BACKEND_DIR) && $(UV) sync --extra dev

install-frontend:
	cd $(FRONTEND_DIR) && $(NPM) ci

# ── Local development ──────────────────────────────────────────────

dev-db:
	cd $(BACKEND_DIR) && $(DOCKER_COMPOSE) up -d postgres

dev-db-down:
	cd $(BACKEND_DIR) && $(DOCKER_COMPOSE) down

dev-api:
	cd $(BACKEND_DIR) && $(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd $(FRONTEND_DIR) && $(NPM) run dev

dev:
	trap 'kill 0' EXIT; $(MAKE) dev-api & $(MAKE) dev-frontend & wait

migrate-up:
	cd $(BACKEND_DIR) && $(UV) run alembic upgrade head

migrate-new:
	cd $(BACKEND_DIR) && $(UV) run alembic revision --autogenerate -m "$(MIGRATION_MESSAGE)"

# ── Generate ───────────────────────────────────────────────────────

requirements-export:
	cd $(BACKEND_DIR) && $(UV) export --no-hashes --no-editable --format=requirements.txt > requirements.txt

openapi-export:
	cd $(BACKEND_DIR) && $(UV) run python scripts/export_openapi.py

frontend-api-gen:
	cd $(FRONTEND_DIR) && $(NPM) run api:gen

generate: openapi-export frontend-api-gen requirements-export

# ── Checks ─────────────────────────────────────────────────────────

format:
	cd $(BACKEND_DIR) && $(UV) run ruff format .
	cd $(FRONTEND_DIR) && $(NPM) run format

lint:
	cd $(BACKEND_DIR) && $(UV) run ruff check .
	cd $(FRONTEND_DIR) && $(NPM) run lint

typecheck:
	cd $(BACKEND_DIR) && $(UV) run mypy --ignore-missing-imports .
	cd $(FRONTEND_DIR) && $(NPM) run typecheck

security:
	cd $(BACKEND_DIR) && $(UV) run bandit -r app -c pyproject.toml -q

test:
	cd $(BACKEND_DIR) && $(UV) run pytest --cov .
	cd $(FRONTEND_DIR) && $(NPM) run test -- --run

frontend-build:
	cd $(FRONTEND_DIR) && $(NPM) run build

check: lint typecheck security test frontend-build bundle-validate

# ── Performance ────────────────────────────────────────────────────

load-test:
	cd $(BACKEND_DIR) && $(UV) run locust -f tests/performance/locustfile.py --headless -u 50 -r 10 -t 2m

# ── Bundle ─────────────────────────────────────────────────────────

bundle-validate:
	databricks bundle validate -t $(TARGET)

bundle-deploy:
	databricks bundle deploy -t $(TARGET)

bundle-run:
	databricks bundle run -t $(TARGET) $(RESOURCE)

bundle-summary:
	databricks bundle summary -t $(TARGET)
