# AGENTS.md

Guidance for AI coding assistants. This is the repo-wide rules file; `CLAUDE.md`
only imports it. Layer-specific guidance: [`backend/AGENTS.md`](backend/AGENTS.md),
[`frontend/AGENTS.md`](frontend/AGENTS.md). Design contract (mission, golden path,
module mechanism, intentional dualities): [`DESIGN.md`](DESIGN.md) — read it before
adding or removing capabilities.

## Project overview

A production-shaped **FastAPI + React starter for Databricks Apps**: chat over a
LangGraph supervisor with pluggable specialist agents (MLflow `ResponsesAgent`
contract), Lakebase persistence, RAG ingestion jobs, MLflow tracing/evals, deployed
exclusively via Databricks Asset Bundles.

**Key principle**: everything is resource-based. Databricks resources are bound in
`resources/*.yml` and injected as env vars — never hardcode resource IDs.

## Repository structure

```
backend/            # Python app (uv) — FastAPI, SQLAlchemy, Alembic; see backend/AGENTS.md
  app/              # api/ chat/ agents/ services/ repositories/ core/ middlewares/ models/ modules/
  alembic/ tests/
frontend/           # React 19 + TS + Vite; see frontend/AGENTS.md
notebooks/          # evals/ (agent eval job), serving/ (ResponsesAgent + deploy), jobs/ (RAG)
resources/          # Bundle resource YAML (app, jobs, database, experiments, …)
resources/modules/  # Optional-capability modules (toggled via databricks.yml include list)
docs/ # Copy-paste recipes for platform features not in the core path
databricks.yml      # Bundle config with dev/staging/prod targets
Makefile            # Root orchestration
```

## Commands

```bash
# Local development
cp backend/env.example backend/.env
make install-backend && make dev-db && make migrate-up
make dev                                  # API + frontend concurrently

# Quality gate — run from backend/ before calling any backend task done
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest --cov

# Regenerate contracts after changing routes/DTOs (openapi + frontend client + requirements)
make generate

# Deployment
databricks bundle validate -t dev && databricks bundle deploy -t dev
databricks bundle run -t dev fastapi_app
```

## Environment & definition of done

- Use `uv` for all backend Python — never `pip install`, `poetry`, or bare
  `python`. Add deps with `cd backend && uv add <pkg>` (dev: `uv add --dev`).
  Never edit `uv.lock` by hand. Tool pins: ruff==0.15.20, mypy==2.1.0.
- The full backend quality gate (above, ~10s) must pass before presenting backend
  work as complete. Run it; do not assume. Claude Code hooks in `.claude/` enforce
  this (lint on edit, gate on stop) — hooks are convenience, CI is authoritative.
- Never weaken a gate to pass it: no lowering coverage thresholds, no skipping or
  deleting failing tests, no `# type: ignore`/`# noqa` without justification, no
  `|| true`, no `git commit --no-verify`.
- Flag — do not silently change — anything touching auth/OBO middleware, dependency
  declarations, lockfiles, `.github/workflows/`, or `.claude/`. New dependencies
  need explicit human sign-off; verify a package exists and is established first.
- Follow `DESIGN.md`'s decision rule for every addition: golden path → core;
  otherwise a module or a docs/ page. Never add a second way to do something
  without a duality-register entry.

## Bundle targets

| Target | Mode | OBO | Log level |
|--------|------|-----|-----------|
| `dev` | development | no | DEBUG |
| `staging` | default | no | INFO |
| `prod` | default | yes | INFO |

## Databricks AI Dev Kit & references

The [AI Dev Kit](https://github.com/databricks-solutions/ai-dev-kit) provides the
`databricks` MCP server (`.mcp.json`) plus skills in `.claude/skills/`.

Docs: [Databricks Apps](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/)
([resources](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/resources),
[auth](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth)) ·
[Asset Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/resources) ·
[MLflow tracing](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/) ·
[Genie Conversation API](https://docs.databricks.com/aws/en/genie/conversation-api) ·
[LangGraph memory](https://docs.langchain.com/oss/python/langgraph/memory)
