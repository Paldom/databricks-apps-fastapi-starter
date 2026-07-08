# AGENTS.md — backend

Guidance for AI coding agents (and new contributors) working in `backend/`.
Repo-wide rules live in the root `AGENTS.md`; design contract in `../DESIGN.md`.

## Architecture

**Authentication**: Databricks Apps forwards user identity via headers
(`X-Forwarded-User`, `X-Forwarded-Email`) → middleware puts it on
`request.state.user`. Local dev: `ENABLE_LOCAL_DEV_AUTH_FALLBACK=true`. OBO: with
`ENABLE_OBO=true` a per-request `WorkspaceClient` is built from the forwarded token.

**Database**: local uses `DATABASE_URL`; deployed, the Apps runtime injects `PG*`
env vars from the Lakebase resource binding and the password comes from the app's
OAuth token via a SQLAlchemy `do_connect` hook — no static secret. Alembic runs
`upgrade head` on every start (`run_app.py`) using the same engine/hook.

**Resource configuration**: never hardcoded. Bundle bindings inject env vars via
`value_from`; all env is read **only** in `app/core/config.py` (`Settings`) —
never scatter `os.getenv()`.

**Chat**: `/api/chat/stream` streams NDJSON (`text-delta`, `tool-call-begin`,
`tool-call-delta`, `done`, `error`) through a LangGraph supervisor
(`app/chat/orchestrator.py`) that routes to specialist tools (`app/chat/tools.py`,
specs in `registry.py` — a specialist registers only when its settings exist).

**Unified agent contract (MLflow Responses-first)**: every backend adapter
implements `AgentAdapter` (`app/agents/contracts.py`) and returns
`AgentInvocationResult` from `async invoke(request: ResponsesAgentRequest)`.
Adapters: `app_adapter` (remote Databricks App), `serving_adapter` (Model Serving,
Responses API), `genie_adapter` (Genie SDK; SQL/attachments preserved in
`custom_outputs`). Downstream trace ids are captured per adapter and surfaced as
OTel span attributes. `POST /api/agents/{backend}/invocations` exposes every
adapter for evaluation and debugging.

**Dependency injection**: all wiring in `app/core/deps.py`; services are built
per-request; the orchestrator is built lazily with agent, checkpointer, tools.

**Observability**: MLflow is the agent plane (central module
`app/core/mlflow_runtime.py`: `configure_mlflow()` at startup, autologging,
per-request trace context, downstream trace-id extraction). OTel is the infra
plane (auto-instrumented HTTP spans + thin manual spans in
`app/core/observability.py`). This is a deliberate duality — see `../DESIGN.md`.

**Evaluation**: agent evals run as Databricks jobs against deployed surfaces:
`databricks bundle run -t dev agent_eval_job`; guide in `notebooks/evals/README.md`.

## Key configuration (`app/core/config.py`)

| Group | Variables |
|-------|----------|
| Database | `DATABASE_URL`, `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` |
| Databricks | `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `ENABLE_DATABRICKS_INTEGRATIONS` |
| Chat | `LANGGRAPH_MEMORY_BACKEND`, `SUPERVISOR_MODEL` |
| Specialists | `APP_AGENT_NAME`, `SERVING_AGENT_ENDPOINT`, `GENIE_SPACE_ID` |
| Knowledge | `KNOWLEDGE_ASSISTANT_ENDPOINT`, `AI_GATEWAY_EMBEDDING_MODEL`, `KNOWLEDGE_VOLUME_ROOT`, `VECTOR_SEARCH_*` |
| MLflow | `MLFLOW_EXPERIMENT_ID` (bundle-provisioned), `MLFLOW_TRACKING_URI`, `MLFLOW_REGISTRY_URI` |

Full list with defaults: `env.example`.

## Modification patterns

- **New API endpoint**: `app/api/<name>_controller.py` with `APIRouter`; register in
  `app/api/router.py`; dependencies from `deps.py`.
- **New agent adapter**: `app/agents/adapters/<name>_adapter.py` implementing
  `AgentAdapter`; register in `factory.py::get_agent_adapter()`; setting in
  `config.py`; env var in `databricks.yml` + `env.example`. It is then available at
  `/api/agents/{backend}/invocations` and in the eval harness automatically.
- **New chat specialist**: tool builder in `chat/tools.py` (`@tool`) delegating to an
  adapter; config guard + spec in `chat/registry.py`; setting + env var as above.
- **New optional capability**: copy `app/modules/_template` (module mechanism —
  see `../DESIGN.md`); resources in `resources/modules/<name>.yml`.
- **New resource binding**: key in `resources/app.yml`; env via `value_from`;
  field in `config.py`; read via `settings.<field>`.
- **Migration**: `make migrate-new MIGRATION_MESSAGE="..."`; auto-runs on deploy.

## Error handling philosophy

- Databricks integrations disabled locally → routes return 503 with a clear
  message; startup never crashes.
- Optional specialists/modules register only when configured; absence degrades to
  "not configured", never to a crash.
- External failures use the taxonomy in `app/core/errors.py`
  (`DatabricksAPIError`, `RequestTimeoutError`, …) mapped to HTTP responses by the
  global exception handler.
- Title generation is best-effort and non-blocking; errors are logged, swallowed.

## Quality gate (run before calling backend work done)

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest --cov
```

mypy is strict with a shrink-only `ignore_errors` ratchet in `pyproject.toml` —
when you touch a listed module, fix its errors and remove it from the list.
