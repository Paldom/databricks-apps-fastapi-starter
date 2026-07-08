# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versioning: the single source of truth is `backend/pyproject.toml`
(`project.version`), bumped with `uv version --bump patch|minor|major` from
`backend/`. Releases are cut by pushing an annotated `vX.Y.Z` tag, which
triggers the release workflow (quality gate → verified build → gated GitHub
Release with wheel/sdist and build provenance). This app is deployed to
Databricks Apps and is never published to PyPI.

## [Unreleased]

### Added

- Toolchain baseline: uv_build packaging, ruff lint/format, strict mypy with
  ratchet, pytest with branch-coverage gate, pre-commit, supply-chain
  hardening, CI aggregator gate, guardrail hooks, and release automation.

### Changed

- Dependency refresh (latest within the 7-day freshness window): fastapi
  0.138, uvicorn 0.49, pydantic 2.13, databricks-sdk 0.119, openai 2.44,
  sqlalchemy 2.0.51, pyarrow 24, secure 2.0, mlflow 3.14, and the pytest/otel
  families; regenerated OpenAPI spec and frontend API client (removes stale
  generated modules). langgraph/langchain 1.x majors deliberately deferred
  (pinned `<1` pending an orchestration migration).

## [0.1.0] - 2026-07-07

### Added

- Initial FastAPI starter for Databricks Apps: LangGraph supervisor chat,
  unified agent adapters (App, Serving, Genie), knowledge/RAG endpoints,
  Lakebase integration, MLflow tracing, and Databricks Asset Bundle deployment.
