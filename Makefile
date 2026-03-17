SHELL := /bin/bash
PYTHON ?= python
UV ?= uv
NPM ?= npm
FRONTEND_DIR := frontend

.PHONY: install install-backend install-frontend \
	dev dev-backend dev-frontend \
	requirements-export openapi-export frontend-api-gen generate \
	backend-lint backend-typecheck backend-test \
	frontend-lint frontend-typecheck frontend-test frontend-build \
	check load-test

# ── Install ────────────────────────────────────────────────────────

install: install-backend install-frontend

install-backend:
	$(UV) pip install -e ".[dev]"

install-frontend:
	cd $(FRONTEND_DIR) && $(NPM) ci

# ── Generate ───────────────────────────────────────────────────────

requirements-export:
	$(UV) export --no-hashes --format=requirements.txt > requirements.txt

openapi-export:
	$(PYTHON) scripts/export_openapi.py

frontend-api-gen:
	cd $(FRONTEND_DIR) && $(NPM) run api:gen

generate: requirements-export openapi-export frontend-api-gen

# ── Dev ────────────────────────────────────────────────────────────

dev-backend:
	$(UV) run uvicorn main:create_app --factory --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd $(FRONTEND_DIR) && $(NPM) run dev

dev:
	bash -lc 'trap "kill 0" EXIT; $(MAKE) dev-backend & $(MAKE) dev-frontend & wait'

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
	cd $(FRONTEND_DIR) && $(NPM) run test

frontend-build:
	cd $(FRONTEND_DIR) && $(NPM) run build

# ── Full check ─────────────────────────────────────────────────────

check: generate backend-lint backend-typecheck backend-test frontend-lint frontend-typecheck frontend-test frontend-build

# ── Performance ────────────────────────────────────────────────────

load-test:
	$(UV) run locust -f tests/performance/locustfile.py --headless -u 50 -r 10 -t 2m
