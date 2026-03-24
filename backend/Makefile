SHELL := /bin/bash
PYTHON ?= python
UV ?= uv
DOCKER_COMPOSE ?= docker compose
MIGRATION_MESSAGE ?= new migration

.PHONY: install dev-api dev-api-otel dev-db dev-db-down \
	migrate-up migrate-new \
	openapi-export \
	lint typecheck test security format load-test

# ── Install ────────────────────────────────────────────────────────

install:
	$(UV) sync --extra dev

# ── Generate ───────────────────────────────────────────────────────

openapi-export:
	$(UV) run python scripts/export_openapi.py

# ── Local development ──────────────────────────────────────────────

dev-db:
	$(DOCKER_COMPOSE) up -d postgres

dev-db-down:
	$(DOCKER_COMPOSE) down

dev-api:
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-api-otel:
	OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
	OTEL_SERVICE_NAME=fastapi-starter-local \
	OTEL_TRACES_SAMPLER=always_on \
	$(UV) run opentelemetry-instrument python run_app.py

migrate-up:
	$(UV) run alembic upgrade head

migrate-new:
	$(UV) run alembic revision --autogenerate -m "$(MIGRATION_MESSAGE)"

# ── Checks ─────────────────────────────────────────────────────────

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run mypy --ignore-missing-imports .

test:
	$(UV) run pytest --cov .

security:
	$(UV) run bandit -r app -c pyproject.toml -q

format:
	$(UV) run ruff format .

# ── Performance ────────────────────────────────────────────────────

load-test:
	$(UV) run locust -f tests/performance/locustfile.py --headless -u 50 -r 10 -t 2m
