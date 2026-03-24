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
- **AI/Chat**: LangGraph supervisor with specialist tools
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
      agents_controller.py # POST /api/agents/{backend}/invocations (eval/debug)
    chat/                  # Chat architecture
      orchestrator.py      # LangGraph supervisor streaming + event translation
      tools.py             # Specialist tool builders (delegate to adapters)
      registry.py          # Specialist specs and routing prompt
      memory.py            # LangGraph checkpointer and message conversion
      title/               # Chat session title generation
    agents/                # Unified agent contract and adapters
      contracts.py         # AgentAdapter protocol, AgentInvocationResult, MLflow types
      response_utils.py    # text_to_response(), response_to_text()
      request_utils.py     # last_user_text()
      factory.py           # get_agent_adapter() dispatcher
      adapters/
        app_adapter.py     # Databricks App (Responses API)
        serving_adapter.py # Model Serving (Responses + legacy chat_completions)
        genie_adapter.py   # Genie (SDK, structured outputs in custom_outputs)
    services/              # Business logic layer
    repositories/          # SQLAlchemy persistence (flush-only, unit-of-work)
    core/
      config.py            # Pydantic Settings — ALL env vars are read here
      bootstrap.py         # App lifespan (startup/shutdown)
      mlflow_runtime.py    # Central MLflow init, trace context, trace ID extraction
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
notebooks/
  evals/
    run_agent_evals.py     # Evaluation notebook entrypoint (parameterised)
    _agent_eval_common.py  # Reusable eval helpers (%run loaded)
    README.md              # Evaluation guide (notebook/job workflow)
resources/                 # Databricks bundle resource definitions (YAML)
  experiment.yml           # MLflow experiment (bound to app)
  evals.yml                # Evaluation job + experiment
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
  value_from: serving-endpoint
- name: JOB_ID
  value_from: app-job
- name: PGHOST
  value_from: lakebase-db
```

Access in code via `Settings` (Pydantic BaseSettings in `backend/app/core/config.py`). **Never scatter `os.getenv()` calls** — all env vars are read in `config.py`.

### Chat Backend Architecture

The `/api/chat/stream` endpoint streams through a LangGraph supervisor agent:

- The supervisor routes to specialist tools based on the user's question
- All specialists delegate to **unified agent adapters** (`app/agents/adapters/`)
- All backends emit the same NDJSON event types: `text-delta`, `tool-call-begin`, `tool-call-delta`, `done`, `error`

### Unified Agent Contract (MLflow Responses-first)

All backend adapters implement the `AgentAdapter` protocol and return `AgentInvocationResult`:

```python
class AgentAdapter(Protocol):
    source: str
    async def invoke(self, request: ResponsesAgentRequest) -> AgentInvocationResult: ...
```

- **App adapter** (`DatabricksAppAdapter`): Calls remote Databricks Apps via Responses API
- **Serving adapter** (`ServingEndpointAdapter`): Defaults to `responses` mode; legacy `chat_completions` supported
- **Genie adapter** (`GenieAdapter`): Wraps Genie SDK; preserves SQL/attachments/conversation IDs in `custom_outputs`
- **Knowledge**: Uses Knowledge Assistant endpoint or direct embed + vector search (no adapter yet)

Downstream trace IDs are captured by each adapter and surfaced as OTel span attributes.

### LangGraph Supervisor

The supervisor routes to four specialist tools (only configured ones are registered):

1. **App Specialist** (optional) — remote Databricks App via `DatabricksAppAdapter`
2. **Serving Specialist** (optional) — remote Model Serving endpoint via `ServingEndpointAdapter` (default: `responses` mode)
3. **Genie Specialist** (optional) — structured data/SQL via `GenieAdapter`
4. **Knowledge Specialist** (optional) — RAG via Knowledge Assistant endpoint or direct embed + vector search

Short-term memory is keyed by `thread_id`. First request seeds full history; subsequent requests append only the latest user message.

### Agent Invocation Route

`POST /api/agents/{backend}/invocations` provides a Responses-compatible surface for evaluation, debugging, and feedback linkage. It accepts `ResponsesAgentRequest` bodies and returns `ResponsesAgentResponse`.

### Dependency Injection

All wiring is in `backend/app/core/deps.py`. Factory functions create services per-request. The chat orchestrator is built lazily with the agent, checkpointer, and tools.

### Observability

- **OpenTelemetry**: HTTP spans (auto-instrumented), manual spans around Databricks calls and tool invocations
- **MLflow** (central module `app/core/mlflow_runtime.py`):
  - Initialized once at startup via `configure_mlflow()`
  - LangChain + OpenAI autologging enabled
  - Trace context (session, user, chat IDs) attached per request via `update_trace_context()`
  - Downstream trace IDs extracted via `extract_trace_id()` (supports both `metadata.trace_id` and `databricks_output.trace.trace_id`)
  - Experiment provisioned by the bundle (`MLFLOW_EXPERIMENT_ID` injected via `value_from: experiment`)
- **AI Gateway**: Usage tracking configured on the endpoint side, not in app code

### Evaluation

Agent evaluations run as **Databricks notebook/job workflows**, targeting deployed
surfaces (not backend internals):

```bash
# Deploy bundle (includes eval job)
databricks bundle deploy -t dev

# Run all eval tasks (app, serving, genie)
databricks bundle run -t dev agent_eval_job
```

Or run `notebooks/evals/run_agent_evals.py` interactively in the workspace.
See [`notebooks/evals/README.md`](notebooks/evals/README.md) for the full guide.

---

## Key Configuration (backend/app/core/config.py)

All settings are in the `Settings` class. Key groups:

| Group | Variables |
|-------|----------|
| Database | `DATABASE_URL`, `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` |
| Databricks | `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `ENABLE_DATABRICKS_INTEGRATIONS` |
| Chat | `LANGGRAPH_MEMORY_BACKEND`, `SUPERVISOR_MODEL` |
| Specialists | `APP_AGENT_NAME`, `SERVING_AGENT_ENDPOINT`, `SERVING_AGENT_API_MODE` (default: `responses`), `GENIE_SPACE_ID` |
| Knowledge | `KNOWLEDGE_ASSISTANT_ENDPOINT`, `AI_GATEWAY_EMBEDDING_MODEL`, `KNOWLEDGE_VOLUME_ROOT`, `VECTOR_SEARCH_*` |
| MLflow | `MLFLOW_EXPERIMENT_ID` (bundle-provisioned), `MLFLOW_TRACKING_URI`, `MLFLOW_REGISTRY_URI` |
| Observability | `ENABLE_CHAT_TITLE_GENERATION` |

See `backend/env.example` for the full list with defaults.

---

## Common Modification Patterns

### Adding a new API endpoint

1. Create controller in `backend/app/api/<name>_controller.py`
2. Define route with `APIRouter`
3. Register in `backend/app/api/router.py`
4. Add dependencies via `Depends()` from `deps.py`

### Adding a new agent backend adapter

1. Create `backend/app/agents/adapters/<name>_adapter.py` implementing `AgentAdapter`
2. Return `AgentInvocationResult` from `invoke()`
3. Register in `backend/app/agents/factory.py` → `get_agent_adapter()`
4. Add config setting in `backend/app/core/config.py`
5. Add env var in `databricks.yml` and `backend/env.example`
6. The adapter is automatically available via `/api/agents/{backend}/invocations` and the eval harness

### Adding a new chat specialist tool

1. Create tool builder in `backend/app/chat/tools.py`
2. Use `@tool` decorator from `langchain_core.tools`
3. Delegate to the corresponding adapter from `backend/app/agents/adapters/`
4. Add config guard + spec in `backend/app/chat/registry.py`
5. Add config setting in `backend/app/core/config.py`
6. Add env var in `databricks.yml` and `backend/env.example`

### Adding a new Databricks resource binding

1. Add resource in `resources/app.yml` with a key (e.g., `my-resource`)
2. Add env var in `databricks.yml` app_config: `value_from: my-resource`
3. Add setting field in `backend/app/core/config.py`
4. Access via `settings.<field_name>` — never raw `os.getenv()`

### Adding a database migration

```bash
make migrate-new MIGRATION_MESSAGE="add my table"
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
