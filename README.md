# databricks-apps-fastapi-starter

[![Snyk Vulnerabilities](https://snyk.io/test/github/Paldom/databricks-apps-fastapi-starter/badge.svg)](https://snyk.io/test/github/Paldom/databricks-apps-fastapi-starter)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Paldom_databricks-apps-fastapi-starter&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=Paldom_databricks-apps-fastapi-starter)
![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/Paldom/databricks-apps-fastapi-starter?utm_source=oss&utm_medium=github&utm_campaign=Paldom%2Fdatabricks-apps-fastapi-starter&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)

[![Databricks](https://img.shields.io/badge/Databricks-Apps-red.svg)](https://docs.databricks.com/en/dev-tools/databricks-apps/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Sample FastAPI application to showcase how to leverage Databricks services.

A production-ready FastAPI template for building data and AI applications on **Databricks Apps**, featuring built-in authentication, database connectivity, and deployment automation. It demonstrates how a FastAPI backend can call various Databricks capabilities including Jobs, Serving endpoints, Delta tables & Volumes, Genie & AgentBricks Knowledge Assistant, AI Gateway, Vector Search and Lakebase.

## Why This Starter?

- **Zero to Production**: Deploy a secure API in minutes, sample CI/CD, IaC.
- **Built for Databricks**: Native integration with Lakebase, Vector Search Index, Unity Catalog, Model Serving, Genie and AgentBricks Knowledge Assistant.
- **Modern Stack**: FastAPI, Pydantic 2.0, SQLAlchemy (async), Alembic. Testing & quality tools like pytest (-asyncio, -cov), Locust, Ruff, MyPy, Bandit.
- **Enterprise Ready**: Built-in auth, governance, security provided by Databricks, with a scalable and layered FastAPI architecture.

## Quickstart

1. [Sign up for a free Databricks account](https://www.databricks.com/learn/free-edition).
2. In the workspace UI open your user icon in the top-right corner,
   choose **Previews** and enable **Lakebase (OLTP)**.
3. Still in the **Previews** menu, enable **User authorization for Databricks Apps**. Optionally, you may also need to enable **On-behalf-of-user authentication**.
4. Create a new PAT, install Databricks CLI, run `databricks configure`.
5. Set keys properly in `.env` based on `.env.example`. Set up Databricks secrets accordingly.
6. Init infrastructure by deploying Databricks Asset Bundle `databricks bundle deploy`.
7. Run database migrations with `alembic upgrade head`.
8. Clone this repository, set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` secrets for deployment with GitHub actions. Run actions.
9. Up & running Apps instance with Lakebase, AI and scaling ecosystem.

## Architecture

This repository implements the core path through a broader Databricks Apps reference architecture.  
The diagram below shows both the pieces demonstrated in this starter and adjacent platform patterns you can add as the project evolves.

[![Reference architecture for the Databricks Apps FastAPI starter](databricks-apps-architecture.svg)](databricks-apps-architecture.svg)

> Scope note: this starter directly covers the Databricks App, FastAPI service layer, Lakebase, Serving, Jobs, AI Gateway, Vector Search, Genie, Knowledge Assistant, Unity Catalog-backed data access, secrets, and DAB-driven provisioning. Some other boxes in the diagram are shown as broader reference patterns rather than scaffolded code in this repo.

## Databricks Services

The legacy example router in `app/api/examples_controller.py` exercises several Databricks services without adding a full feature layer around them:

- **Serving Endpoint** -- queries an MLflow model that can scale seamlessly with no latency. Recommended for complex but critical tasks.
- **Databricks Jobs** -- triggers a job and returns its output. Recommended for heavy duty background tasks, like media conversion, parsing, where latency is not a problem, but a custom cluster can be useful.
- **AI Gateway** -- gateway for embeddings or foundation model's AI query.
- **Vector Search** -- stores and searches embeddings in a vector search index.
- **Delta Table** -- read and persists data in a Unity Catalog Delta table.
- **Volume** -- reads and writes files in a Unity Catalog's Volume.
- **Genie** -- ask natural language questions about your data using the Conversation API.

### Genie conversation API

Databricks Genie lets applications query data using natural language.
When `ENABLE_LEGACY_API=true`, the demo exposes
`/legacy/v1/genie/{space_id}/ask` to start a conversation and
`/legacy/v1/genie/{space_id}/{conversation_id}/ask` for follow-up questions.
Databricks Apps automatically provide the host URL and token used by these
endpoints.

Infrastructure for these services is described using a Databricks Asset Bundle
(`databricks.yml`).  The `notebooks/serving` directory defines the simple
MLflow model that backs the serving endpoint and `notebooks/jobs` contains the
notebook executed by the job resource.

## Setup

### Prerequisites
- Python 3.11+ with uv configured
- Databricks CLI configured
- Access to a Databricks workspace

### Local Development

Clone the repository:
```bash
git clone https://github.com/Paldom/databricks-apps-fastapi-starter.git
cd databricks-apps-fastapi-starter
```

Configure environment:
```bash
cp .env.example .env
# Edit .env with your Databricks credentials
```

Install dependencies and start the app:
```bash
uv sync --extra dev
source .venv/bin/activate
uv run uvicorn app.main:app --reload
```

> **Note:** When changing dependencies, regenerate both `uv.lock` and `requirements.txt`:
> ```bash
> uv lock
> uv export --no-hashes --no-editable --format=requirements.txt > requirements.txt
> ```

### Static analysis

Run Ruff, mypy and Bandit:

```bash
ruff check .
mypy --ignore-missing-imports .
bandit -r . -q
```

### Testing

Run the unit test suite with coverage:

```bash
pytest --cov .
```

### Performance testing

Run the Locust benchmark:

```bash
make load-test
```
Set `HOST`, `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID` and
`DATABRICKS_CLIENT_SECRET` to target a remote deployment.

### Database migrations

Alembic is the **sole schema authority** — the application never creates or
alters tables at runtime.  Migrations must be applied before the application
starts.  The `app.yaml` command runs `alembic upgrade head` automatically
before launching the server.

The database URL is resolved from (in order):
1. The `DATABASE_URL` environment variable (if set).
2. Constructed from the `LAKEBASE_*` settings.

Create a new migration:

```bash
alembic revision --autogenerate -m "my change"
```

Apply pending migrations:

```bash
alembic upgrade head
```

### Caching

The Todo module uses **repository-layer caching with explicit invalidation**:

- **Memory backend** (default) for local development — no extra services needed.
- **Redis backend** for production/shared deployments — set `CACHE_BACKEND=redis`
  and configure the `CACHE_REDIS_*` variables.
- Reads go through a **cache-aside** pattern: check cache first, fall back to DB
  on miss, then populate the cache.
- Writes **explicitly invalidate** the relevant cache entries after flushing to
  the database. List caches use a **versioned key** — a version counter is
  bumped on every write, so old list snapshots expire naturally via TTL.
- Cache failures are swallowed and logged; they never break CRUD correctness.
- GET endpoints return `ETag` and `Cache-Control: private, no-cache` headers.
  Clients can send `If-None-Match` to receive `304 Not Modified` when the data
  has not changed.

### Transaction architecture

Each request gets a **session with an active transaction** via FastAPI's
dependency injection.  The transaction commits when the request completes
successfully, or rolls back on exception.

- **Repositories** never commit — they only `flush()`.
- The **request-scoped session dependency** owns the transaction lifecycle.
- The **user middleware** uses its own independent session so user upserts
  commit regardless of request outcome.

## Architecture

The application follows a layered architecture under the `app/` package:

```
app/
  main.py                         # FastAPI app factory + global error handler
  api/
    api.py                        # Central router registry
    health_controller.py          # /healthcheck, /databasehealthcheck, /health/live, /health/ready
    user_controller.py            # /userInfo
    examples_controller.py        # Legacy Databricks example routes
  services/
    project_service.py            # Project CRUD and pagination
    chat_service.py               # Chat CRUD and search
    document_service.py           # Document listing and uploads
    user_settings_service.py      # Per-user settings
    chat_stream_service.py        # Streaming chat responses
  repositories/
    project_repository.py         # SQLAlchemy project persistence
    chat_repository.py            # SQLAlchemy chat persistence
    document_repository.py        # SQLAlchemy document persistence
    user_repository.py            # User upsert (flush only)
    user_settings_repository.py   # Settings persistence
  models/
    __init__.py                   # Model registry (imports all ORM models)
    base.py                       # Re-exports from core.db.base
    project_model.py              # Project ORM model
    chat_session_model.py         # Chat session ORM model
    message_model.py              # Chat message ORM model
    file_record_model.py          # Uploaded file ORM model
    user_model.py                 # AppUser ORM model (users table)
    user_settings_model.py        # User settings ORM model
    user_dto.py                   # CurrentUser, UserInfo
    health_dto.py                 # Health response models
  core/
    bootstrap.py                  # Lifespan (startup/shutdown) — no schema creation
    config.py                     # Pydantic Settings + Databricks secrets
    deps.py                       # Shared runtime / request dependencies
    errors.py                     # AppError hierarchy
    logging.py                    # Logging setup (OTel-compatible, idempotent)
    observability.py              # Thin OTel helpers (tracer, meter, spans, metrics)
    db/                           # Centralised database infrastructure
      __init__.py                 # Public API re-exports
      url.py                      # Single-source DB URL builder
      base.py                     # Base, TimestampMixin, AuditMixin
      engine.py                   # Async engine + session factory
      deps.py                     # FastAPI dependencies (session, engine)
    databricks/                   # Databricks SDK adapters
      workspace.py                # WorkspaceClient singleton
      serving.py                  # ServingAdapter
      jobs.py                     # JobsAdapter
      ai_gateway.py               # AiGatewayAdapter (AsyncOpenAI)
      vector_search.py            # VectorSearchAdapter
      sql_delta.py                # SqlDeltaAdapter
      genie.py                    # GenieAdapter (httpx)
      uc_files.py                 # UcFilesAdapter
  middlewares/
    request_context.py            # Request-ID propagation + safe span attrs
    request_size.py               # ASGI body size enforcement
    user_info.py                  # Auth header extraction + user upsert
    workspace_client.py           # OBO WorkspaceClient
    security_headers.py           # OWASP security headers
```

### Dependency Flow

```
Public API route -> Service -> Repository -> Shared deps (app.state)
Legacy example route -> Adapter / DB session -> Shared deps (app.state)
```

- **Example routes** stay intentionally flat, closer to the original starter repo.
- **Services** are used for the main app features, not for the Databricks demos.
- **Repositories** handle persistence (SQLAlchemy) — flush only, never commit.
- **Adapters** (`app/core/databricks/`) wrap low-level SDK calls with error mapping, timeouts, and thread bridging.

### Router Registry

`app/api/public/` contains the frontend-facing `/api` contract. `app/api/api.py`
registers the legacy routes that are mounted under `/legacy/v1` when
`ENABLE_LEGACY_API=true`. Health checks remain unversioned at `/healthcheck`,
`/databasehealthcheck`, and `/health/*`.

### Error Handling

Adapters raise typed `AppError` subclasses (e.g., `ServingEndpointError`, `ConfigurationError`). A global exception handler in `app/main.py` converts these to appropriate HTTP responses. Controllers do not need try/except blocks for adapter errors.

### DI and Testing

Runtime resources are stored in a single `app.state.runtime` container during bootstrap. DI factory functions in `app/core/deps.py` read from that runtime container, making tests simple:
- **Route tests**: use `dependency_overrides` and `TestClient`
- **Feature service tests**: construct with mock repositories (no FastAPI needed)
- **Adapter tests**: construct with mock SDK clients

Root-level `main.py` and `api.py` are compatibility shims that re-export from the `app` package.

## API versioning

All API endpoints are served under the `/api/v1` prefix (canonical). The legacy
`/v1` prefix is also supported for backward compatibility but is not included
in the OpenAPI schema. Future versions of the API will use `/api/v2`, etc.

Example requests:
```bash
# Canonical
curl http://localhost:8000/api/v1/userInfo -H "X-Forwarded-User: me"
curl http://localhost:8000/api/v1/todos/ -H "X-Forwarded-User: me"

# Legacy (still works)
curl http://localhost:8000/v1/userInfo -H "X-Forwarded-User: me"
```

### API Routes and Documentation

Once running, access the interactive API documentation, generated by FastAPI at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## Configuration

The application reads its settings from environment variables using a
Pydantic `Settings` model defined in `app/core/config.py`.  When running locally you
can place these variables in a `.env` file which is automatically loaded.
If a value is not provided via the environment, the settings object will
attempt to look it up in Databricks secrets using the same key name.

Configuration keys:

- `DATABASE_URL` - optional override; if set, used as-is for the database
  connection string (takes precedence over `LAKEBASE_*` settings)
- `SERVING_ENDPOINT_NAME`
  optional; used by the serving, AI Gateway, and vector-search demo endpoints
- `JOB_ID`
- `VECTOR_SEARCH_ENDPOINT_NAME`
- `VECTOR_SEARCH_INDEX_NAME`
- `LAKEBASE_HOST`
- `LAKEBASE_PORT`
- `LAKEBASE_DB`
- `LAKEBASE_USER`
- `LAKEBASE_PASSWORD`
- `ENVIRONMENT` - set to `production` to disable the OpenAPI documentation
- `LOG_LEVEL` - Python logging level used by the application
- `VOLUME_ROOT` - root UC volume path for the demo file endpoints
- `ENABLE_OBO` - set to `true` to accept `X-Forwarded-Access-Token`
- `CACHE_ENABLED` - enable/disable the cache (default `true`)
- `CACHE_BACKEND` - `memory` (default) or `redis`
- `CACHE_NAMESPACE` - key prefix for cache entries
- `CACHE_DEFAULT_TTL` - default TTL in seconds
- `CACHE_TODO_LIST_TTL` - TTL for todo list cache (default `60`)
- `CACHE_TODO_DETAIL_TTL` - TTL for todo detail cache (default `120`)
- `CACHE_TIMEOUT` - backend operation timeout in seconds
- `CACHE_REDIS_ENDPOINT` - Redis host (when using `redis` backend)
- `CACHE_REDIS_PORT` - Redis port (default `6379`)
- `CACHE_REDIS_DB` - Redis database number
- `CACHE_REDIS_PASSWORD` - Redis password (optional)

Create a `.env` file based on `env.example`:

```bash
cp env.example .env
```

Edit `.env` or set the variables directly in the environment.  When
deploying on Databricks, you can also store these values in your secret
scope so that the application loads them automatically when environment
variables are absent.

### Health and readiness

- `GET /healthcheck` and `GET /health/live` report basic process health.
- `GET /databasehealthcheck` reports database-only readiness.
- `GET /health/ready` returns a lightweight readiness report (checks client
  initialization, **no network calls**).
- `GET /health/deep` runs full dependency probes (database query, AI
  embedding, vector search describe) and caches results for
  `HEALTH_READY_CACHE_TTL` seconds (default 30). Rate-limited to 10/minute.

Readiness returns HTTP `200` when all required checks are healthy and HTTP `503`
when any required check is failing or not configured. Optional integrations such
as AI Gateway, Vector Search, cache, and broker are diagnostic-only by default:
they surface as `not_configured` or `fail` in the response without crashing the
endpoint or forcing a `503` on their own.

### Databricks secrets

Databricks SDK secrets are returned base64 encoded.  The traditional
`dbutils.secrets.get("scope", "key")` helper yields the plain text
value, but `w().secrets.get_secret()` from `databricks.sdk` returns an
object whose `value` field is base64 encoded.  The `get_secret` helper in
`app/core/config.py` abstracts this difference. Use `get_secret` whenever
you need a secret at runtime:

```python
from app.core.config import get_secret

token = get_secret("MY_TOKEN", scope="starter_scope")
```

## Security

The application applies common HTTP security headers using the
[`secure`](https://github.com/TypeError/secure) library. These headers
include HSTS, content type, frame and referrer policies in line with
OWASP recommendations.

### Dependency management

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

**Version policy:**
- Production dependencies in `pyproject.toml` use exact pins (e.g.,
  `fastapi==0.135.1`) except for OpenTelemetry packages and `aiocache`
  which use compatible-release bounds.
- Dev dependencies use unpinned or range-based specifiers for flexibility.
- `uv.lock` is the resolved lockfile and is committed to the repository.

**`requirements.txt` is generated — do not edit it manually.** It is
produced by:

```bash
uv export --no-hashes --no-editable --format=requirements.txt > requirements.txt
```

CI verifies that `requirements.txt` matches the lockfile on every PR.
After changing any dependency in `pyproject.toml`, regenerate both files:

```bash
uv lock
uv export --no-hashes --no-editable --format=requirements.txt > requirements.txt
```

**Security scanning:**
- [Snyk](https://snyk.io/) runs on every PR and weekly, failing on
  high/critical vulnerabilities. Results are uploaded to GitHub Code
  Scanning. Requires a `SNYK_TOKEN` repository secret.
- [Dependabot](https://docs.github.com/en/code-security/dependabot)
  proposes weekly grouped PRs for dependency and GitHub Actions updates.
- The `.snyk` policy file contains vulnerability ignores. Never add broad
  wildcard ignores; always scope to a specific vulnerability ID, path,
  and expiry date.

### Rate limiting and abuse controls

Expensive legacy example endpoints are rate-limited using an in-memory
fixed-window strategy. Rate-limit keys are derived from the authenticated
Databricks user identity, falling back to IP and client host.

| Endpoint | Default limit |
|----------|--------------|
| `POST /legacy/v1/serving` | 20/minute |
| `POST /legacy/v1/job` | 5/minute |
| `POST /legacy/v1/embed` | 20/minute |
| `POST /legacy/v1/vector/store` | 10/minute |
| `POST /legacy/v1/vector/query` | 20/minute |
| `POST /legacy/v1/genie/{space_id}/ask` | 5/minute |
| `POST /legacy/v1/genie/{space_id}/{conv}/ask` | 20/minute |
| `GET /health/ready` | 60/minute |
| `GET /health/deep` | 10/minute |

Disable rate limiting for development with `RATE_LIMIT_ENABLED=false`.

> **Note:** Rate limiting uses an in-memory backend and is per-process,
> not globally distributed. For production deployments with multiple
> workers, consider a Redis-backed limiter.

### Request limits

A global ASGI middleware enforces maximum request body sizes:

| Content type | Default limit | Setting |
|-------------|---------------|---------|
| JSON / other | 1 MiB | `MAX_REQUEST_BODY_BYTES` |
| Multipart (uploads) | 10 MiB | `MAX_UPLOAD_BYTES` |

File uploads are read in chunks to avoid unbounded memory usage.
Volume paths are validated to prevent path traversal.

### Timeout controls

All downstream service calls have configurable timeouts:

| Setting | Default |
|---------|---------|
| `SERVING_TIMEOUT_SECONDS` | 30 |
| `JOB_TIMEOUT_SECONDS` | 120 |
| `VECTOR_TIMEOUT_SECONDS` | 30 |
| `GENIE_TIMEOUT_SECONDS` | 30 |
| `OPENAI_TIMEOUT_SECONDS` | 30 |

Synchronous SDK calls run via `asyncio.to_thread()` wrapped with
`asyncio.wait_for()`. On timeout the underlying thread may continue
(Python limitation) but the async caller is unblocked immediately.

### Known limitations

- Rate limiting is **in-memory, per-process** — not globally distributed.
- Thread-based timeouts protect the event loop but the SDK thread may
  leak until it completes naturally.
- Sensitive headers (`Authorization`, `X-Forwarded-Access-Token`) are
  never logged. Security events include `request_id`, `user_id`,
  `client_ip`, and `route`.

### Authentication

Databricks Apps authenticates users and forwards identity via HTTP headers.
The application's `user_info_middleware` reads these headers and maintains
a local `users` table for user persistence:

| Header | Maps to |
|--------|---------|
| `X-Forwarded-User` | `user.id` (primary key) |
| `X-Forwarded-Email` | `user.email` |
| `X-Forwarded-Preferred-Username` | `user.preferred_username` |

Protected endpoints (e.g. `/api/v1/userInfo`, `/api/v1/todos/`) require the
`X-Forwarded-User` header and return **401** when it is absent.

For local development, either use the Databricks local app runner (which
forwards headers automatically) or pass headers manually:

```bash
curl http://localhost:8000/api/v1/todos/ \
  -H "X-Forwarded-User: me@example.com" \
  -H "X-Forwarded-Email: me@example.com"
```

Set `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET`
so that the app can generate cross-app authentication headers using
`WorkspaceClient.config.authenticate()`. The same variables are consumed by the
Locust load tests.

### User authorization scopes

To allow the backend to act on behalf of the signed-in workspace user, enable
the **Access tokens** scope in your app configuration. When this scope is
selected Databricks forwards the user's token in the `X-Forwarded-Access-Token`
header so the middleware can initialize a `WorkspaceClient` with the user's
identity. See the [Databricks Apps authentication docs](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth) for details.

## Observability

This application ships with production-grade observability powered by
**OpenTelemetry** and **Databricks Apps telemetry**.  When deployed to
Databricks Apps with telemetry enabled, traces, metrics, and correlated
application logs are automatically exported to Unity Catalog system tables.

### What is captured

| Signal | Source |
|--------|--------|
| HTTP request spans | Auto-instrumented (FastAPI, httpx, requests) |
| SQL spans | Auto-instrumented (SQLAlchemy) |
| Dependency boundary spans | Manual spans around Serving, Jobs, AI Gateway, Vector Search, Genie, SQL Delta calls |
| App lifecycle spans | `app.startup`, `app.shutdown` with per-component child spans |
| Health / readiness | `health.ready` with per-dependency child spans |
| Todo operations | `todo.list`, `todo.create`, `todo.update`, `todo.delete` |
| Log correlation | Every log line includes `trace_id`, `span_id`, and `request_id` |
| Metrics | Startup/shutdown duration, health check counts, dependency call latency, todo operation counts |

### Enabling telemetry in Databricks

1. Open your Databricks Apps instance in the workspace UI.
2. Go to **Settings > Telemetry** and toggle telemetry **on**.
3. Select a Unity Catalog **catalog** and **schema** where telemetry
   tables will be created.
4. Optionally set a **table prefix** (ASCII-only characters).

**Requirements and constraints:**

- The telemetry catalog must be in the **same region** as the workspace.
- Only **managed Delta tables** are supported.
- Catalog, schema, and table prefix names must use **ASCII characters only**.
- The identity running the app needs `USE CATALOG`, `USE SCHEMA`, and
  `CREATE TABLE` permissions on the target catalog and schema.
- Consider enabling **predictive optimization** on the telemetry schema
  for better query performance on the Delta tables.

### Telemetry tables

Databricks Apps telemetry creates three tables:

| Table | Contents |
|-------|----------|
| `otel_logs` | Application log records with trace/span correlation |
| `otel_metrics` | Counter and histogram metric data points |
| `otel_spans` | Distributed trace spans |

> **Note:** The `/logz` endpoint and Apps UI log viewer show live logs but
> these are **not durable** after compute shutdown.  The system tables above
> are the persistent observability store.

### Sample validation SQL

After enabling telemetry and sending a few requests, verify data is flowing:

```sql
-- Recent application logs
SELECT time, service_name, trace_id, span_id, attributes
FROM <catalog>.<schema>.otel_logs
ORDER BY time DESC
LIMIT 50;

-- Recent trace spans
SELECT trace_id, span_id, parent_span_id, name, start_time, end_time, attributes
FROM <catalog>.<schema>.otel_spans
ORDER BY start_time DESC
LIMIT 50;

-- Metrics summary
SELECT metric_name, start_time, value, attributes
FROM <catalog>.<schema>.otel_metrics
ORDER BY start_time DESC
LIMIT 50;
```

Replace `<catalog>.<schema>` with your configured telemetry destination.
If you set a table prefix, prepend it to the table names (e.g.,
`<prefix>_otel_logs`).

### Local development

When running locally without `OTEL_EXPORTER_OTLP_ENDPOINT`, all OTel API
calls resolve to no-ops -- the app starts and runs normally with zero
overhead.

To enable local tracing (optional):

```bash
# Run a local Jaeger instance
docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one

# Set the endpoint and run the app
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
OTEL_SERVICE_NAME=fastapi-starter-local \
opentelemetry-instrument uvicorn main:app --reload
```

Open http://localhost:16686 to explore traces.

## Deployment

The repository includes `.github/workflows/deploy.yml` which deploys the app
to Databricks using the Databricks CLI. Configure the required secrets and push
to the `main` branch to trigger a deployment.

Set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` secrets before first run.

### Migration-first startup

The application does **not** create database tables at runtime. Alembic
migrations should be applied before the server starts. The `app.yaml` entry
point attempts `alembic upgrade head` before launching uvicorn, but it will
still start the app if the database is unavailable so liveness and readiness
endpoints can report the failure explicitly.

For fresh environments or CI pipelines where the database is reachable, run
migrations explicitly:

```bash
alembic upgrade head
```

## Databricks Asset Bundle

To validate and deploy the infrastructure defined in `databricks.yml`, run:

```bash
databricks bundle validate
databricks bundle deploy -e dev
```

Use the Databricks CLI to provide values for the placeholder secrets:

```bash

databricks secrets put-secret starter_scope LAKEBASE_PASSWORD
databricks secrets put-secret starter_scope OPENAI_KEY
```
