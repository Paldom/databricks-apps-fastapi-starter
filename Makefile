SHELL := /bin/bash
NPM ?= npm
FRONTEND_DIR ?= frontend
BACKEND_DIR ?= backend

.PHONY: install install-backend install-frontend \
	dev dev-api dev-api-otel dev-backend dev-frontend dev-db dev-db-down \
	migrate-up migrate-new \
	openapi-export frontend-api-gen generate \
	backend-lint backend-typecheck backend-test \
	frontend-lint frontend-typecheck frontend-test frontend-build \
	lint format typecheck security test check load-test \
	bundle-validate

# ── Install ────────────────────────────────────────────────────────

install: install-backend install-frontend

install-backend:
	$(MAKE) -C $(BACKEND_DIR) install

install-frontend:
	cd $(FRONTEND_DIR) && $(NPM) ci

# ── Generate ───────────────────────────────────────────────────────

openapi-export:
	$(MAKE) -C $(BACKEND_DIR) openapi-export

frontend-api-gen:
	cd $(FRONTEND_DIR) && $(NPM) run api:gen

generate: openapi-export frontend-api-gen

# ── Local development ──────────────────────────────────────────────

dev-db:
	$(MAKE) -C $(BACKEND_DIR) dev-db

dev-db-down:
	$(MAKE) -C $(BACKEND_DIR) dev-db-down

dev-api:
	$(MAKE) -C $(BACKEND_DIR) dev-api

dev-api-otel:
	$(MAKE) -C $(BACKEND_DIR) dev-api-otel

dev-backend: dev-api

dev-frontend:
	cd $(FRONTEND_DIR) && $(NPM) run dev

dev:
	bash -lc 'trap "kill 0" EXIT; $(MAKE) dev-api & $(MAKE) dev-frontend & wait'

migrate-up:
	$(MAKE) -C $(BACKEND_DIR) migrate-up

migrate-new:
	$(MAKE) -C $(BACKEND_DIR) migrate-new

# ── Backend checks ─────────────────────────────────────────────────

backend-lint:
	$(MAKE) -C $(BACKEND_DIR) lint

backend-typecheck:
	$(MAKE) -C $(BACKEND_DIR) typecheck

backend-test:
	$(MAKE) -C $(BACKEND_DIR) test

# ── Frontend checks ────────────────────────────────────────────────

frontend-lint:
	cd $(FRONTEND_DIR) && $(NPM) run lint

frontend-typecheck:
	cd $(FRONTEND_DIR) && $(NPM) run typecheck

frontend-test:
	cd $(FRONTEND_DIR) && $(NPM) run test -- --run

frontend-build:
	cd $(FRONTEND_DIR) && $(NPM) run build

# ── Bundle validation ──────────────────────────────────────────────

bundle-validate:
	databricks bundle validate -t dev

# ── Combined developer targets ─────────────────────────────────────

lint: backend-lint frontend-lint

format:
	$(MAKE) -C $(BACKEND_DIR) format
	cd $(FRONTEND_DIR) && $(NPM) run format

typecheck: backend-typecheck frontend-typecheck

security:
	$(MAKE) -C $(BACKEND_DIR) security

test: backend-test frontend-test

check: generate lint typecheck security test frontend-build bundle-validate

# ── Performance ────────────────────────────────────────────────────

load-test:
	$(MAKE) -C $(BACKEND_DIR) load-test
