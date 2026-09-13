# AGENTS.md: backend

Guidance for coding agents and new contributors working in `backend/`. Repo-wide rules are in the root
`AGENTS.md`; the design contract in `../DESIGN.md`.

## Architecture

- **Identity.** Databricks Apps forwards `X-Forwarded-User` and `X-Forwarded-Email`; `user_info` middleware
  upserts the user and sets `request.state.user`; `get_current_user` guards every route that touches user data.
  Local dev uses the fallback user while `ENVIRONMENT=development` unless `ENABLE_LOCAL_DEV_AUTH_FALLBACK=false`.
  With `ENABLE_OBO=true` a per-request `WorkspaceClient` is built from the forwarded token (`workspace_client`
  middleware) and tools read it from a context var, never from tool arguments.
- **Database.** Lakebase Autoscaling through the injected `PG*` variables; the password is the app's OAuth token,
  minted per connection in `core/db/engine.py`. Alembic runs `upgrade head` at every start (`run_app.py`) in the
  app-owned schema under an advisory lock. One initial migration; new ones via `make migrate-new`.
- **Configuration.** Bundle bindings inject environment variables; `core/config.py` (`Settings`) is the only
  reader. `env.example` is generated from it.
- **Databricks clients.** `core/databricks/` is the complete client layer: `genie.py`, `knowledge_assistant.py`,
  `serving.py`, `jobs.py`, `uc_files.py`, `vector_search.py`, `ai_gateway.py`, each with spans and error mapping,
  sync SDK calls offloaded through `_async_bridge.run_sync`. Outside this layer the SDK appears only where an identity is built: the engine's OAuth hook, the workspace-client factory and the on-behalf-of middleware.
- **Agents.** `agents/adapters/` implement `AgentAdapter` (`agents/contracts.py`) on the MLflow `ResponsesAgent`
  request and response types: `app_adapter` (remote Databricks App), `serving_adapter` (Model Serving),
  `genie_adapter` (conversation handling and normalisation on top of `core/databricks/genie.py`).
  `POST /api/agents/{backend}/invocations` exposes each adapter and the supervisor for evaluation.
- **Chat.** `chat/orchestrator.py` streams a LangGraph supervisor turn (`chat/agent.py`, no checkpointer) as
  NDJSON events; `chat/tools.py` builds one tool per configured specialist (`chat/registry.py`); `chat/parts.py`
  accumulates the ordered content parts the controller persists before `done`. Per-turn state (trace id, Genie
  conversation) is a dict shared with the tool tasks (`core/context.py`).
- **Persistence.** `api → services → repositories → models`; repositories flush only, the request commits;
  keyset cursors in `core/pagination.py`.
- **Observability.** `core/mlflow_runtime.py` (autolog, root span, trace metadata) is the agent plane;
  `core/observability.py` (thin OpenTelemetry spans) and `core/logging.py` (request, session, user and trace ids
  on every application log line) are the infra plane.

## Modification patterns

- **New route:** `api/<name>_controller.py` with an `APIRouter`, registered in `api/router.py`; dependencies from
  `core/deps.py`; then `make generate` and commit the regenerated client.
- **New Databricks call:** a method in the matching `core/databricks/` client (span, `run_sync`, error class),
  a test with a fake SDK object under `tests/core/databricks/`.
- **New specialist:** an adapter in `agents/adapters/`, a tool builder in `chat/tools.py`, a `SpecialistSpec` in
  `chat/registry.py`, a `Settings` field, the commented binding and env entry in `resources/fastapi_app.app.yml`.
- **Errors:** raise the taxonomy in `core/errors.py`; the handler returns a generic message plus the trace id,
  never exception text. Tools raise `ToolException` with a fixed public text.

## Quality gate

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
```

Tests mock external I/O at the adapter boundary only; never stub `langgraph`, `mlflow` or `sqlalchemy` with
fake modules. Import-linter enforces the layer contracts.
