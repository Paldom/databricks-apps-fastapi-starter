# AGENTS.md

This file provides guidance to AI coding assistants (Claude Code, Cursor, Copilot, etc.) when working with this repository.

---

## Project Overview

A **production-ready FastAPI template** for building data and AI applications on **Databricks Apps**. The backend is Python (FastAPI + SQLAlchemy + Alembic), the frontend is React + TypeScript + Vite. Deployment uses **Databricks Asset Bundles** exclusively.

**Key principle**: Everything is resource-based. Databricks resources (serving endpoints, Lakebase databases, volumes, Genie spaces) are bound to the app via `resources/app.yml` and injected as environment variables. Never hardcode resource IDs.

---

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy (async), Alembic, Pydantic
- **Frontend**: React 19, TypeScript, Vite
- **Database**: Lakebase (Databricks-managed Postgres) in production, Docker Postgres locally
- **AI/Chat**: LangGraph supervisor with specialist tools, OpenAI-compatible fallback
- **Deployment**: Databricks Asset Bundles (`databricks.yml` + `resources/*.yml`)
- **Testing**: pytest (backend), vitest (frontend)
- **Linting**: ruff (backend), ESLint (frontend)
- **Type checking**: mypy (backend), TypeScript strict (frontend)

---

## Repository Structure

```
backend/                   # Python project (uv, pyproject.toml)
  app/
    api/                   # FastAPI route controllers (mounted at /api)
    chat/                  # Chat architecture
      backends/            # ChatBackend Protocol, Factory, OpenAI/LangGraph implementations
      orchestrator/        # LangGraph supervisor graph, memory, events, specialist tools
      title/               # Chat session title generation
    services/              # Business logic layer
    repositories/          # SQLAlchemy persistence (flush-only, unit-of-work)
    agents/                # Deployable agent models (e.g. minimal_serving_agent)
    core/
      config.py            # Pydantic Settings — ALL env vars are read here
      bootstrap.py         # App lifespan (startup/shutdown)
      runtime.py           # AppRuntime dataclass (engine, clients, checkpointer)
      deps.py              # FastAPI dependency injection wiring
      integrations.py      # Lazy Databricks client initialization
      observability.py     # OpenTelemetry helpers (safe_attr, tag_exception)
      databricks/          # SDK adapters (serving, jobs, genie, vector search, etc.)
      db/                  # Async SQLAlchemy engine, session, URL builder
    middlewares/            # Auth, OBO, security headers, request size
    models/                # ORM models and DTOs
  alembic/                 # Database migrations (auto-run on deploy)
  tests/                   # pytest test suite
frontend/                  # React + TypeScript + Vite
resources/                 # Databricks bundle resource definitions (YAML)
databricks.yml             # Bundle config with dev/staging/prod targets
Makefile                   # Root orchestration
```

---

## Commands

```bash
# Local development
cp backend/env.example backend/.env
make install-backend          # uv sync
make dev-db                   # Docker Postgres
make migrate-up               # alembic upgrade head
make dev                      # API + frontend concurrently

# Backend only
cd backend && uv run uvicorn app.main:app --reload

# Testing
make test                     # pytest
make lint                     # ruff check
make typecheck                # mypy

# Deployment
databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run -t dev fastapi_app
```

---

## Architecture & Design Patterns

### Authentication Flow

1. **Deployed**: Databricks Apps forwards user identity via headers (`X-Forwarded-User`, `X-Forwarded-Email`). The auth middleware extracts these into `request.state.user`.
2. **Local dev**: `ENABLE_LOCAL_DEV_AUTH_FALLBACK=true` provides a fallback user. No credentials needed.
3. **OBO (on-behalf-of)**: When `ENABLE_OBO=true`, a per-request `WorkspaceClient` is created from the user's forwarded token for user-scoped operations.

### Database Connection

- **Local**: `DATABASE_URL` env var with static credentials
- **Deployed (Lakebase)**: `PGHOST`/`PGDATABASE`/`PGUSER` injected by the `lakebase-db` resource binding. Password is provided dynamically via the app's OAuth token using a SQLAlchemy `do_connect` event hook. No static password secret needed.
- **Migrations**: Run automatically on every deploy/restart (`run_app.py` calls `alembic upgrade head` before starting the server). Alembic reuses the app's engine with the same OAuth hook.

### Resource Configuration Pattern

Resources are **never hardcoded**. All resource IDs come from environment variables configured in `databricks.yml`:

```yaml
# Resource bindings in resources/app.yml inject values via valueFrom
- name: SERVING_ENDPOINT_NAME
  valueFrom: serving-endpoint
- name: JOB_ID
  valueFrom: app-job
- name: PGHOST
  valueFrom: lakebase-db
```

Access in code via `Settings` (Pydantic BaseSettings in `backend/app/core/config.py`). **Never scatter `os.getenv()` calls** — all env vars are read in `config.py`.

### Chat Backend Architecture

The `/api/chat/stream` endpoint uses a **Protocol/Factory** pattern:

- `ChatBackend` Protocol defines the streaming interface
- `ChatBackendFactory` selects the implementation based on `CHAT_BACKEND` setting
- **OpenAI Compat backend**: Direct `AsyncOpenAI.chat.completions.create()` — simple fallback
- **LangGraph Supervisor backend**: StateGraph with specialist tools and short-term memory

All backends emit the same NDJSON event types: `text-delta`, `tool-call-begin`, `tool-call-delta`, `done`, `error`.

### LangGraph Supervisor

The supervisor routes to four specialist tools (only configured ones are registered):

1. **App Specialist** (always available) — in-process LLM for synthesis/fallback
2. **Serving Specialist** (optional) — remote Model Serving endpoint (supports `chat_completions` and `responses` API modes)
3. **Genie Specialist** (optional) — structured data/SQL via Genie Conversation API
4. **Knowledge Specialist** (optional) — RAG via AI Gateway embeddings + Vector Search

Short-term memory is keyed by `thread_id`. First request seeds full history; subsequent requests append only the latest user message.

### Dependency Injection

All wiring is in `backend/app/core/deps.py`. Factory functions create services per-request:

```python
def get_chat_stream_service(request: Request) -> ChatStreamService:
    factory = ChatBackendFactory(settings=..., ai_client=..., ...)
    backend = factory.create()
    return ChatStreamService(backend)
```

### Observability

- **OpenTelemetry**: HTTP spans (auto-instrumented), manual spans around Databricks calls, SQL spans
- **MLflow**: LangGraph/OpenAI autolog when `MLFLOW_EXPERIMENT_ID` is set
- **AI Gateway**: Usage tracking configured on the endpoint side, not in app code

---

## Key Configuration (backend/app/core/config.py)

All settings are in the `Settings` class. Key groups:

| Group | Variables |
|-------|----------|
| Database | `DATABASE_URL`, `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` |
| Databricks | `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `ENABLE_DATABRICKS_INTEGRATIONS` |
| Chat | `CHAT_BACKEND`, `LANGGRAPH_MEMORY_BACKEND`, `SUPERVISOR_MODEL`, `APP_SPECIALIST_MODEL` |
| Specialists | `SERVING_SPECIALIST_ENDPOINT`, `SERVING_SPECIALIST_API_MODE`, `GENIE_SPACE_ID` |
| Knowledge | `AI_GATEWAY_EMBEDDING_MODEL`, `KNOWLEDGE_VOLUME_ROOT`, `VECTOR_SEARCH_*` |
| Observability | `MLFLOW_EXPERIMENT_ID`, `ENABLE_CHAT_TITLE_GENERATION` |

See `backend/env.example` for the full list with defaults.

---

## Common Modification Patterns

### Adding a new API endpoint

1. Create controller in `backend/app/api/<name>_controller.py`
2. Define route with `APIRouter`
3. Register in `backend/app/api/router.py`
4. Add dependencies via `Depends()` from `deps.py`

### Adding a new chat specialist tool

1. Create tool in `backend/app/chat/orchestrator/tools/<name>.py`
2. Use `@tool` decorator from `langchain_core.tools`
3. Add config guard + registration in `backend/app/chat/orchestrator/tools/__init__.py`
4. Add config setting in `backend/app/core/config.py`
5. Add env var in `databricks.yml` and `backend/env.example`

### Adding a new Databricks resource binding

1. Add resource in `resources/app.yml` with a key (e.g., `my-resource`)
2. Add env var in `databricks.yml` app_config: `valueFrom: my-resource`
3. Add setting field in `backend/app/core/config.py`
4. Access via `settings.<field_name>` — never raw `os.getenv()`

### Adding a database migration

```bash
cd backend && make migrate-new MIGRATION_MESSAGE="add my table"
```

Migrations run automatically on deploy. For local dev: `make migrate-up`.

---

## Error Handling Philosophy

- **Databricks integrations disabled locally**: Routes return `503` with clear message, never crash startup
- **Optional specialists**: Only registered when backing resources are configured
- **LangGraph fallback**: If LangGraph init fails, factory falls back to OpenAI compat backend
- **Title generation**: Best-effort, non-blocking, errors are logged and swallowed
- **Database**: If not configured, startup skips DB init and logs a warning

---

## Bundle Targets

| Target | Mode | OBO | Log level |
|--------|------|-----|-----------|
| `dev` | development | no | DEBUG |
| `staging` | default | no | INFO |
| `prod` | default | yes | INFO |

---

## Databricks AI Dev Kit

The [Databricks AI Dev Kit](https://github.com/databricks-solutions/ai-dev-kit) provides the `databricks` MCP server (configured in `.mcp.json`) with 50+ tools for interacting with Databricks, including:

- SQL execution and warehouse management
- Unity Catalog operations (tables, volumes, schemas)
- Jobs and workflow management
- Model serving endpoints
- Genie spaces and AI/BI dashboards
- Databricks Apps deployment

Skills installed via the AI Dev Kit (in `.gemini/skills/`) provide patterns for Spark Declarative Pipelines, Structured Streaming, Databricks Jobs, Asset Bundles, Unity Catalog, SQL, Genie, MLflow, Model Serving, Vector Search, and Databricks Apps.

---

## References

- [Databricks Apps docs](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/)
- [Databricks Apps resources](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/resources)
- [Databricks Apps auth](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth)
- [Databricks Asset Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/resources)
- [Genie Conversation API](https://docs.databricks.com/aws/en/genie/conversation-api)
- [MLflow tracing](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/)
- [AI Gateway](https://docs.databricks.com/aws/en/ai-gateway/)
- [LangGraph memory](https://docs.langchain.com/oss/python/langgraph/memory)
