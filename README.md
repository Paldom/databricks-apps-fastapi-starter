# databricks-apps-fastapi-starter

[![Snyk Vulnerabilities](https://snyk.io/test/github/Paldom/databricks-apps-fastapi-starter/badge.svg)](https://snyk.io/test/github/Paldom/databricks-apps-fastapi-starter)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Paldom_databricks-apps-fastapi-starter&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=Paldom_databricks-apps-fastapi-starter)
[![Databricks](https://img.shields.io/badge/Databricks-Apps-red.svg)](https://docs.databricks.com/en/dev-tools/databricks-apps/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A FastAPI + React starter for data and AI apps on **Databricks Apps**. One `databricks bundle deploy`
provisions everything the app needs and starts it: a Lakebase Postgres project for app state, an AI Search
endpoint and a serverless ingestion job for uploaded documents, MLflow experiments with traces stored in
Unity Catalog, app telemetry tables, and the app itself with its resource bindings. The chat is a LangGraph
supervisor that routes to specialists (your own documents, Genie, a Model Serving agent, a remote app or a
Knowledge Assistant), streams over NDJSON and stores every turn server-side.

## Quickstart

### Local development (no workspace needed)

```bash
git clone https://github.com/Paldom/databricks-apps-fastapi-starter.git
cd databricks-apps-fastapi-starter
make setup            # uv sync, npm ci, pre-commit hooks, agent skills
cp backend/env.example backend/.env
make dev-db && make migrate-up && make dev
```

Open `http://localhost:5173` (frontend) or `http://localhost:8000/api/docs`. A fallback dev user is used while
`ENVIRONMENT=development` unless `ENABLE_LOCAL_DEV_AUTH_FALLBACK=false` (the bundle sets it to `false`);
Databricks integrations stay off unless `ENABLE_DATABRICKS_INTEGRATIONS=true` and the CLI is authenticated.

### Deploy to a workspace

Requirements: Databricks CLI 1.16 (validated; the bundle requires `>= 1.15`), Node 22 (see `.nvmrc`), `uv`, a workspace with Databricks Apps and
Lakebase, and a Unity Catalog catalog you may create schemas in (`rag_catalog_name`, default `main`).

```bash
databricks auth login --host <workspace-url> --profile <profile>
export DATABRICKS_CONFIG_PROFILE=<profile>
databricks bundle validate -t dev --profile "$DATABRICKS_CONFIG_PROFILE"
databricks bundle deploy   -t dev --profile "$DATABRICKS_CONFIG_PROFILE"
```

That single deploy runs the `prebuild` hook (frontend build into `backend/public`), creates or updates every
resource under `resources/`, starts the app (`lifecycle.started`) and runs the `postdeploy` hook that grants
the app's service principal the Unity Catalog privileges it needs. The app reports the deployed commit at
`/api/health` (`version`).

The first deploy takes a few minutes longer: the Lakebase project and the AI Search endpoint are provisioned,
and the app image is built from `pyproject.toml` + `uv.lock`. Migrations run at every app start under an
advisory lock. The `postdeploy` hook needs `jq`. The supervisor and embedding models (`supervisor_model`,
`ai_gateway_embedding_model`) are pay-per-token Foundation Model endpoints that must already exist in the
workspace; the bundle binds them but does not create them.

## What a target provisions

| Resource                       | File                          | dev                                      | prod                                                 |
| ------------------------------ | ----------------------------- | ---------------------------------------- | ---------------------------------------------------- |
| App `fastapi-starter-<suffix>` | `resources/app.yml`           | MEDIUM compute, docs and examples on     | MEDIUM compute, OBO on, examples off                 |
| Lakebase project + database    | `resources/database.yml`      | 0.5 to 2 CU, suspends after 5 min        | 1 to 4 CU, never suspends                            |
| Schema + volume                | `resources/unity_catalog.yml` | `<catalog>.<prefix>starter_rag`, uploads | `<catalog>.starter_rag` (staging: `starter_rag_stg`) |
| AI Search endpoint             | `resources/vector_search.yml` | STANDARD (billed while it exists)        | STANDARD                                             |
| Ingestion job                  | `resources/compute.yml`       | serverless, file-arrival trigger on      | serverless, file-arrival trigger on                  |
| Experiments (app, evals)       | `resources/experiment.yml`    | traces in UC tables `app_mlflow_*`       | same                                                 |
| Evaluation job                 | `resources/evals.yml`         | serverless, one run per target           | same                                                 |
| Serving agent job + experiment | `resources/serving_agent.yml` | run on demand                            | run on demand                                        |
| App telemetry tables           | `resources/app.yml`           | `app_logs`, `app_metrics`, `app_traces`  | same                                                 |

Development mode prefixes schema, job and experiment names per developer; app names, the Lakebase project id
and the AI Search endpoint name are shared per target. The ingestion job's Delta Sync index is created by the
job on its first run (an index cannot be declared before its source table exists). Staging matches prod except
OBO off, a smaller Lakebase endpoint that suspends, and no destroy protection. The dev Lakebase project has
`purge_on_delete: true`, so `bundle destroy -t dev` purges the shared dev database. The bundle root is the
deploying identity's home folder (`/Workspace/Users/<principal>/.bundle/...`).

Cost notes: the AI Search endpoint and a non-suspending Lakebase endpoint are the standing costs; the app
compute runs while the app is started; jobs and Model Serving scale to zero.

## Architecture

```
frontend/  React 19 + TypeScript + Vite, assistant-ui runtime, generated Orval client (built into backend/public)
backend/   FastAPI, SQLAlchemy async + Alembic (Lakebase), LangGraph supervisor, MLflow tracing
notebooks/ jobs/rag_ingestion_job.py (serverless), evals/ (mlflow.genai.evaluate), serving/ (ResponsesAgent)
resources/ bundle resources; databricks.yml holds the variables and the three targets
scripts/   postdeploy_grants.sh (UC privileges for the app service principal), setup-agentic.sh
```

Backend layers are enforced by import-linter: `api → services → repositories → models`, and `core` never
imports `chat` or `agents`.

### App resource bindings

Everything the app talks to is bound in `resources/app.yml` and arrives as environment variables; nothing is
hardcoded.

| Binding            | Kind             | Permission               | Env var                                                                            |
| ------------------ | ---------------- | ------------------------ | ---------------------------------------------------------------------------------- |
| `postgres`         | Lakebase         | `CAN_CONNECT_AND_CREATE` | `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGSSLMODE` (injected by the platform) |
| `experiment`       | MLflow           | `CAN_MANAGE`             | `MLFLOW_EXPERIMENT_ID`                                                             |
| `app-job`          | Job              | `CAN_MANAGE_RUN`         | `JOB_ID` (ingestion job, started after a document delete)                          |
| `uc-volume`        | Volume           | `WRITE_VOLUME`           | `VOLUME_ROOT`                                                                      |
| `supervisor-model` | Serving endpoint | `CAN_QUERY`              | `SUPERVISOR_MODEL`                                                                 |
| `embedding-model`  | Serving endpoint | `CAN_QUERY`              | `AI_GATEWAY_EMBEDDING_MODEL`                                                       |

The database password is the app's OAuth token, minted on every connection. Table privileges on the schema
(reading the AI Search index, writing MLflow traces) cannot be expressed as app bindings; the `postdeploy`
hook grants `USE_SCHEMA` and `SELECT` on the bundle schema and `MODIFY` on the `app_mlflow_*` trace tables to
the app's service principal. It fails the deploy when the app has no service principal yet; re-run it with
`bash scripts/postdeploy_grants.sh <target>`.

### Optional specialists

The Genie space, a Knowledge Assistant, the serving agent and a remote app are bound per target, because an
empty binding fails the deploy. Add the env entry and the binding to a target; lists merge by `name`:

```yaml
targets:
  prod:
    variables:
      genie_space_id: <space id>
    resources:
      apps:
        fastapi_app:
          config:
            env:
              - name: GENIE_SPACE_ID
                value_from: genie-space
          resources:
            - name: genie-space
              genie_space:
                space_id: ${var.genie_space_id}
                permission: CAN_RUN
```

The same pattern applies to `knowledge-assistant` and `serving-agent` (`serving_endpoint`, `CAN_QUERY`) and
`app-agent` (`app`, `CAN_USE`); the commented block in `resources/app.yml` lists them.

## Chat

- `POST /api/chat/stream` runs one turn of the supervisor for an owned chat (`thread_id` is the chat id from
  `POST /api/projects/{id}/chats`). The backend keeps the transcript: it loads the stored history, appends the
  new user message, streams NDJSON events (`text-delta`, `tool-call-begin`, `tool-call-delta`, `tool-result`,
  `heartbeat`, `done`, `error`) and stores the assistant message with its content parts before sending `done`.
- `GET /api/chats/{id}/messages` returns the stored turns (keyset pagination, oldest first); the frontend
  renders the same parts it streamed (text and tool calls with results).
- Limits: a per-tool deadline (45 s), a turn deadline (90 s, the Apps ingress cuts requests at about two
  minutes), a heartbeat every 15 s, three concurrent turns per instance and one turn per chat. Tool failures
  reach the model and the client with a fixed public text; details stay in the log with the trace id.
- Persistence: the user message is stored when the turn starts, the assistant message when it completes. A
  turn that fails or times out leaves the user message and sends an `error` event with the trace id.
- Genie follow-ups reuse the conversation of the chat; a turn that outlives the deadline can be polled at
  `GET /api/chats/{id}/genie/{messageId}`.
- `POST /api/agents/supervisor/invocations` is a stateless Responses-compatible surface of the same agent
  (used by evaluations and curl); `/api/agents/{app|serving_endpoint|genie}/invocations` call one specialist.

### Documents

Upload through `POST /api/knowledge/files` (PDF, DOCX, PPTX, images). The file lands in the bundle volume under
a per-user path with a `pending` record; the file-arrival trigger starts the ingestion job, which parses with
`ai_parse_document`, chunks, writes the Delta tables and creates or syncs the Delta Sync index.
`GET /api/documents/{id}/status` probes the index and turns the record `ingested` once its chunks are
searchable (the sidebar polls it); `GET /api/documents` lists. `DELETE /api/documents/{id}` removes the file,
starts the job (which drops the rows of missing files) and deletes the record. Retrieval is filtered by the uploading user; AI Search
has no row-level security, so that filter is the isolation.

A Knowledge Assistant (Agent Bricks) is a shared corpus by design: when `KNOWLEDGE_ASSISTANT_ENDPOINT` is
bound, the knowledge specialist asks it instead of the per-user index, and the uploads index is only registered
with it when `knowledge_assistant_name` is set on purpose.

### Alternatives worth knowing

| Need                          | This template                                     | Alternative                                                   |
| ----------------------------- | ------------------------------------------------- | ------------------------------------------------------------- |
| Routing between specialists   | In-app LangGraph supervisor (code, testable)      | Agent Bricks Supervisor Agent, bound as a specialist          |
| Retrieval over your documents | Ingestion job + Delta Sync index, per-user filter | Knowledge Assistant (managed, shared corpus), Lakebase Search |
| Hosting the model logic       | Databricks Apps (this backend)                    | Model Serving via `notebooks/serving` (see below)             |

### Showcase endpoints

`ENABLE_EXAMPLES=true` (dev only by default) mounts `/api/examples/*`: Genie ask, Knowledge Assistant ask,
embeddings, AI Search query, a job run (`202` + `GET /api/examples/job/{run_id}` polling), a Model Serving
query (`SERVING_ENDPOINT_NAME`), UC volume upload and download. They are authenticated, use the caller's
identity when OBO is on and the app's otherwise, and return `503` with a clear message when the resource is
not configured.

## Observability

- Traces: every turn is an MLflow trace whose root span (`chat.turn`, type AGENT) carries the question, the
  answer, `user.id`, `session.id` and the token counts. Traces are stored in Unity Catalog next to the app
  telemetry (`<schema>.app_mlflow_*`); reading them (UI, `search_traces`, evaluations) needs a SQL warehouse,
  which the bundle does not create (`sql_warehouse_id` for the evaluation job; the app never reads traces).
- App telemetry: `telemetry_export_destinations` writes OTel logs, metrics and spans to `app_logs`,
  `app_metrics` and `app_traces`. `MLFLOW_TRACE_ENABLE_OTLP_DUAL_EXPORT=true` keeps MLflow traces flowing to
  the experiment as well; without it MLflow exports only over OTLP.
- Logs: application lines carry `request_id`, `session_id`, `user_id`, `trace_id` and `span_id`
  (`OTEL_PYTHON_LOG_FORMAT` in the bundle, a handler filter in `core/logging.py`); uvicorn's access log keeps
  its own format.

## Evaluations

`databricks bundle run -t <target> agent_eval_job` evaluates each entry of `eval_targets` (JSON, default: the
app) with `Correctness`, `Safety` and `RelevanceToQuery` judged by `judge_model`, on the inline sample set or the
UC dataset in `agent_eval_dataset_name`. Results land in the evals experiment.

The job needs `sql_warehouse_id` (the evals experiment stores traces in Unity Catalog; the bundle creates no
warehouse). The app target is called through the Apps ingress, which rejects a job's own credential, so it
also needs `eval_secret_scope`: a secret scope holding `client-id` and `client-secret` of a service principal
that has `CAN_USE` on the app:

```bash
databricks secrets create-scope eval-app --profile "$DATABRICKS_CONFIG_PROFILE"
databricks secrets put-secret eval-app client-id --string-value <client id> --profile "$DATABRICKS_CONFIG_PROFILE"
databricks secrets put-secret eval-app client-secret --profile "$DATABRICKS_CONFIG_PROFILE"   # prompts
```

From a machine with `databricks auth login` the same predict function works with the user's OAuth token. The
`endpoint` and `genie` targets work with the job identity. A UC dataset (`agent_eval_dataset_name`) needs the
`databricks-agents` package, declared in the job environment.

## Serving agent (optional)

`notebooks/serving/agent.py` is an MLflow `ResponsesAgent` that forwards to a Foundation Model endpoint over
chat completions. `databricks bundle run -t <target> deploy_serving_agent` logs it with
`resources=[DatabricksServingEndpoint(...)]` (managed credentials, no secret scope), registers it in Unity
Catalog and creates or updates the `serving-agent-<suffix>` endpoint (scale to zero). Then set
`serving_agent_endpoint`, add the `serving-agent` binding to the target (see optional specialists) and redeploy;
the supervisor gains the `serving_endpoint` tool.

## Authentication

Databricks Apps authenticate every request and forward `X-Forwarded-User` and `X-Forwarded-Email`; the
backend trusts them only inside Apps (or in local development). With `ENABLE_OBO=true` (prod target) the
forwarded user token is used for Genie, uploads and the showcase routes; model calls and retrieval use the app
identity. Scopes are declared in `user_api_scopes`; a deploy applies scope changes, and users consent to the
new scopes at their next login. Calling the API from outside a browser: `curl -H "Authorization: Bearer
$(databricks auth token --profile <profile> | jq -r .access_token)" <app-url>/api/health`.

Egress: the backend only talks to the workspace (model endpoints, AI Search, Lakebase, Unity Catalog files).
The browser loads the Geist fonts from Google Fonts (`frontend/index.html`); self-host them if that is not
acceptable in your network.

## Local development

```bash
make dev-db          # Postgres 17 in Docker (matches Lakebase)
make migrate-up      # alembic upgrade head
make dev             # uvicorn on :8000 and Vite on :5173 (proxies /api)
make check           # pre-commit (ruff, mypy, import-linter, prettier, eslint), bandit, pytest, vitest, build
make generate        # OpenAPI export, frontend client, env.example (commit the result)
make migrate-new MIGRATION_MESSAGE="add table"
```

`backend/env.example` is generated from the `Settings` class; copy it to `backend/.env`. Databricks-backed
features need `ENABLE_DATABRICKS_INTEGRATIONS=true` and an authenticated CLI profile
(`DATABRICKS_CONFIG_PROFILE`).

## CI/CD

- `ci.yml` runs `make check` plus the frontend typecheck and coverage thresholds, a generated-file drift check
  and `bundle validate` for the three targets; it needs the
  repository variables `DATABRICKS_HOST` and `DATABRICKS_CLIENT_ID` (a service principal with a GitHub OIDC
  federation policy). No client secret is stored.
- `deploy.yml` deploys `dev` on every push to `main` after the gate, and `staging`/`prod` on manual dispatch
  inside GitHub environments; it then polls `/api/health` until the app serves the pushed commit.
- All actions are pinned by SHA. `snyk-security.yml` runs when the repository variable `SNYK_ENABLED` is
  `true` and the `SNYK_TOKEN` secret exists; `sonar.yml` needs the `SONAR_TOKEN` secret (delete the workflow
  if you do not use SonarCloud).

## Security

- Request size limits, security headers and a strict CORS default (no wildcard; `CORS_ALLOW_ORIGINS` lists
  explicit origins) are middlewares in `backend/app/middlewares`.
- API errors carry a generic message and the trace id, never exception text; `/api/health` reports a failing
  dependency as `Unavailable` and logs the cause.
- Secrets never live in the repo: `detect-secrets` runs in pre-commit, `.env` is ignored, and Model Serving
  authenticates through model resources instead of secret scopes.
