SHELL := /bin/bash
PYTHON ?= python
UV ?= uv
NPM ?= npm
DOCKER_COMPOSE ?= docker compose
FRONTEND_DIR ?= frontend
API_CLIENT_DIR ?= client
MIGRATION_MESSAGE ?= new migration

.PHONY: install install-backend install-frontend \
	dev dev-api dev-backend dev-frontend dev-db dev-db-down dev-compose \
	migrate-up migrate-new \
	requirements-export openapi-export frontend-api-gen generate \
	backend-lint backend-typecheck backend-test \
	frontend-lint frontend-typecheck frontend-test frontend-build \
	lint format typecheck security test check load-test

# ── Install ────────────────────────────────────────────────────────

install: install-backend install-frontend

install-backend:
	$(UV) sync --extra dev

install-frontend:
	cd $(FRONTEND_DIR) && $(NPM) ci

# ── Generate ───────────────────────────────────────────────────────

requirements-export:
	$(UV) export --no-hashes --format=requirements.txt > requirements.txt

openapi-export:
	$(UV) run python scripts/export_openapi.py

frontend-api-gen:
	cd $(API_CLIENT_DIR) && $(NPM) run api:gen

generate: requirements-export openapi-export frontend-api-gen

# ── Local development ──────────────────────────────────────────────

dev-db:
	$(DOCKER_COMPOSE) up -d postgres

dev-db-down:
	$(DOCKER_COMPOSE) down

dev-api:
	$(UV) run uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-backend: dev-api

dev-frontend:
	cd $(FRONTEND_DIR) && $(NPM) run dev

dev-compose:
	$(DOCKER_COMPOSE) up --build api postgres

dev:
	bash -lc 'trap "kill 0" EXIT; $(MAKE) dev-api & $(MAKE) dev-frontend & wait'

migrate-up:
	$(UV) run alembic upgrade head

migrate-new:
	$(UV) run alembic revision --autogenerate -m "$(MIGRATION_MESSAGE)"

# ── Backend checks ─────────────────────────────────────────────────

backend-lint:
	$(UV) run ruff check .

backend-typecheck:
	$(UV) run mypy --ignore-missing-imports .

backend-test:
	$(UV) run pytest --cov .

# ── Frontend checks ────────────────────────────────────────────────

frontend-lint:
	cd $(FRONTEND_DIR) && $(NPM) run lint

frontend-typecheck:
	cd $(FRONTEND_DIR) && $(NPM) run typecheck

frontend-test:
	cd $(FRONTEND_DIR) && $(NPM) run test -- --run

frontend-build:
	cd $(FRONTEND_DIR) && $(NPM) run build

# ── Combined developer targets ─────────────────────────────────────

lint: backend-lint frontend-lint

format:
	$(UV) run ruff format .
	cd $(FRONTEND_DIR) && $(NPM) run format

typecheck: backend-typecheck frontend-typecheck

security:
	$(UV) run bandit -r . -q

test: backend-test frontend-test

check: generate lint typecheck security test frontend-build

# ── Performance ────────────────────────────────────────────────────

load-test:
	$(UV) run locust -f tests/performance/locustfile.py --headless -u 50 -r 10 -t 2m
