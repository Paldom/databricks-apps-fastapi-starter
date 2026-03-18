# databricks-apps-fastapi-starter

[![Snyk Vulnerabilities](https://snyk.io/test/github/Paldom/databricks-apps-fastapi-starter/badge.svg)](https://snyk.io/test/github/Paldom/databricks-apps-fastapi-starter)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Paldom_databricks-apps-fastapi-starter&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=Paldom_databricks-apps-fastapi-starter)
![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/Paldom/databricks-apps-fastapi-starter?utm_source=oss&utm_medium=github&utm_campaign=Paldom%2Fdatabricks-apps-fastapi-starter&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)

[![Databricks](https://img.shields.io/badge/Databricks-Apps-red.svg)](https://docs.databricks.com/en/dev-tools/databricks-apps/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A production-ready FastAPI template for building data and AI applications on **Databricks Apps**, featuring built-in authentication, database connectivity, and deployment automation. It demonstrates how a FastAPI backend can call various Databricks capabilities including Jobs, Serving endpoints, Delta tables & Volumes, Genie & AgentBricks Knowledge Assistant, AI Gateway, Vector Search and Lakebase.

## Bundle-First Deployment

This repository uses **Databricks Asset Bundles** as the single deployment contract. All infrastructure (app, serving endpoint, job, database, vector search, secret scope) is defined in modular YAML files under `resources/` and deployed with `databricks bundle deploy`.

There is no workspace Repo sync, no Git credential registration, and no manual `databricks apps deploy` commands. The committed `databricks.yml` and `resources/*.yml` files are the source of truth.

### What this means

- **Runtime app config** (command, env vars) is defined in the bundle YAML via a complex `app_config` variable, not a standalone `app.yaml`
- **Resource-backed env vars** (`SERVING_ENDPOINT_NAME`, `JOB_ID`, `VOLUME_ROOT`, secrets) are injected via `valueFrom` app resource bindings
- **Three targets** are supported: `dev`, `staging`, `prod`
- **CI/CD** uses `databricks bundle validate/deploy/run` exclusively

## Architecture

[![Reference architecture for the Databricks Apps FastAPI starter](databricks-apps-architecture.svg)](databricks-apps-architecture.svg)

### Bundle resources

| Resource | File | Purpose |
|----------|------|---------|
| FastAPI App | `resources/app.yml` | App definition with resource bindings and runtime config |
| Serving Endpoint | `resources/serving.yml` | MLflow model serving (StarterModel) |
| Job + Cluster | `resources/compute.yml` | Spark job for background tasks |
| Lakebase Instance | `resources/database.yml` | PostgreSQL-compatible OLTP database |
| Vector Search Index | `resources/vector_search.yml` | Delta Sync vector index |
| Secret Scope | `resources/secrets.yml` | Stores `LAKEBASE_PASSWORD` and `OPENAI_KEY` |

### App resource bindings

The app is granted access to specific Databricks resources with least-privilege permissions:

| Binding name | Resource type | Permission |
|-------------|---------------|------------|
| `serving-endpoint` | Serving endpoint | `CAN_QUERY` |
| `app-job` | Job | `CAN_MANAGE_RUN` |
| `uc-volume` | UC Volume | `WRITE_VOLUME` |
| `openai-key` | Secret | `READ` |
| `lakebase-password` | Secret | `READ` |
| `knowledge-assistant` | Serving endpoint | `CAN_QUERY` |

These bindings are used with `valueFrom` in the app's env config, so the app receives resolved values as environment variables at runtime.

### Application layers

```
app/
  api/public/          # Frontend-facing API routes (mounted at /api)
  services/            # Business logic
  repositories/        # SQLAlchemy persistence (flush only)
  core/databricks/     # Databricks SDK adapters (serving, jobs, vector search, etc.)
  core/db/             # Async SQLAlchemy engine, session, URL builder
  core/security/       # Rate limiting, path validation
  middlewares/         # Auth, OBO, security headers, request size
  models/              # ORM models and DTOs
```

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- [Databricks CLI](https://docs.databricks.com/en/dev-tools/cli/install.html) >= 0.283.0
- Access to a Databricks workspace with:
  - **Databricks Apps** enabled
  - **Lakebase (OLTP)** preview enabled (Previews menu)
  - **User authorization for Databricks Apps** preview enabled

## Local Development

The local development workflow is **API on the host + Postgres in Docker**. Databricks integrations are optional and disabled by default for local work.

### Host API + Docker Postgres

```bash
git clone https://github.com/Paldom/databricks-apps-fastapi-starter.git
cd databricks-apps-fastapi-starter

cp env.example .env
make dev-db
uv sync --extra dev
make migrate-up
make dev-api
```

With the defaults from `env.example`, the following work locally without Databricks credentials:

- `http://localhost:8000/docs`
- `http://localhost:8000/api/health/live`
- `http://localhost:8000/api/health/ready`
- `http://localhost:8000/health/live`
- `http://localhost:8000/health/ready`
- authenticated `/api` routes via the development fallback user

### Optional remote-integrated local mode

To exercise real Databricks-dependent routes locally, set:

- `ENABLE_DATABRICKS_INTEGRATIONS=true`
- `DATABRICKS_HOST`
- one of:
  - `DATABRICKS_TOKEN`
  - `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET`
- any route-specific config such as `SERVING_ENDPOINT_NAME`, `JOB_ID`, `VECTOR_SEARCH_*`, or `KNOWLEDGE_ASSISTANT_ENDPOINT`

You can also use the Databricks local app runner:

```bash
databricks apps run-local --prepare-environment --debug
```

In offline local mode, Databricks example routes return clear `503` responses instead of breaking startup or unrelated endpoints.

### Static analysis

```bash
make lint
make typecheck
make security
```

### Testing

```bash
make test
```

### Performance testing

```bash
make load-test
```

Set `HOST`, `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET` to target a remote deployment.

### Database migrations

Alembic is the sole schema authority. Migrations must be applied before the application starts.

Database configuration precedence is:

1. `DATABASE_URL`
2. `PGHOST` / `PGPORT` / `PGDATABASE` / `PGUSER` / `PGPASSWORD`
3. legacy `LAKEBASE_HOST` / `LAKEBASE_PORT` / `LAKEBASE_DB` / `LAKEBASE_USER` / `LAKEBASE_PASSWORD`

Common migration commands:

```bash
make migrate-up
```

Create a new migration:

```bash
make migrate-new MIGRATION_MESSAGE="my change"
```

### OpenAPI export

Export the API spec for client codegen:

```bash
make openapi-export
```

## One-Time Bootstrap

### 1. Create a service principal

Create a service principal in your Databricks account for CI/CD:

```bash
databricks service-principals create --display-name "fastapi-starter-deployer"
```

### 2. Configure authentication

**Option A: GitHub OIDC (recommended)**

Follow the [Databricks GitHub OIDC docs](https://docs.databricks.com/aws/en/dev-tools/auth/provider-github) to configure workload identity federation. This avoids storing long-lived secrets.

**Option B: Client secret fallback**

Generate a client secret for the service principal and store it as a GitHub secret.

### 3. Configure local CLI auth

```bash
databricks configure
# Enter your workspace URL and authenticate
```

### 4. Deploy bundle infrastructure

```bash
databricks bundle validate -t dev
databricks bundle deploy -t dev
```

### 5. Populate secrets

The bundle creates the secret scope but does not populate values. Set them manually:

```bash
databricks secrets put-secret starter_scope_dev LAKEBASE_PASSWORD
databricks secrets put-secret starter_scope_dev OPENAI_KEY
```

### 6. Run database migrations

```bash
alembic upgrade head
```

### 7. Start the app

```bash
databricks bundle run -t dev fastapi_app
```

## GitHub Actions Setup

### Required secrets

| Secret | Description |
|--------|-------------|
| `DATABRICKS_HOST` | Workspace URL (e.g., `https://dbc-123.cloud.databricks.com`) |
| `DATABRICKS_CLIENT_ID` | Service principal client ID |
| `DATABRICKS_CLIENT_SECRET` | Service principal client secret (not needed if using OIDC) |
| `SNYK_TOKEN` | Snyk API token (for security scanning) |
| `SONAR_TOKEN` | SonarCloud token (for code quality) |

### OIDC configuration

The deploy workflow requests `id-token: write` permission for GitHub OIDC. If your workspace is configured for OIDC, `DATABRICKS_CLIENT_SECRET` is not needed.

### CI workflows

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `ci.yml` | PR, push to main | Ruff, Mypy, Bandit, pytest, frontend build, OpenAPI drift check, bundle validate |
| `deploy.yml` | Push to main, manual | `bundle validate` + `bundle deploy` + `bundle run` |
| `ci-load-test.yml` | PR, manual | Locust performance test (50 users, 60s) |
| `snyk-security.yml` | PR, push, weekly | Dependency and code security scanning |
| `sonar.yml` | PR, push to main | SonarCloud code quality |

## Deploy Commands

### Validate

```bash
databricks bundle validate -t dev
databricks bundle validate -t staging
databricks bundle validate -t prod
```

### Deploy

```bash
databricks bundle deploy -t dev
databricks bundle deploy -t staging
databricks bundle deploy -t prod
```

### Run the app

```bash
databricks bundle run -t dev fastapi_app
databricks bundle run -t prod fastapi_app
```

### View deployed resources

```bash
databricks bundle summary -t dev
```

## Bundle Targets

| Target | Mode | App name | Docs enabled | OBO |
|--------|------|----------|-------------|-----|
| `dev` | development | `databricks-apps-fastapi-starter` | yes | no |
| `staging` | default | `databricks-apps-fastapi-starter-stg` | no | no |
| `prod` | default | `databricks-apps-fastapi-starter-prod` | no | yes |

## Databricks Services

The legacy example router in `app/api/examples_controller.py` exercises several Databricks services:

- **Serving Endpoint** -- queries an MLflow model with seamless scaling
- **Databricks Jobs** -- triggers a job and returns its output
- **AI Gateway** -- gateway for embeddings or foundation model AI queries
- **Vector Search** -- stores and searches embeddings in a vector search index
- **Delta Table** -- reads and persists data in a Unity Catalog Delta table
- **Volume** -- reads and writes files in a Unity Catalog Volume
- **Genie** -- natural language questions about your data using the Conversation API
- **Knowledge Assistant** -- queries an Agent Bricks Knowledge Assistant via the Responses API (both sync and streaming)

## Configuration

The application reads settings from environment variables using Pydantic `Settings` in `app/core/config.py`. When running locally, place variables in a `.env` file. When deployed via bundles, resource-backed values are injected automatically via `valueFrom`.

Key configuration:

| Variable | Description | Bundle-injected |
|----------|-------------|----------------|
| `ENABLE_DATABRICKS_INTEGRATIONS` | Enables Databricks-only routes and lazy client initialization | Set to `true` in bundle app envs |
| `ENABLE_LOCAL_DEV_AUTH_FALLBACK` | Enables development-only fallback identity when forwarded headers are absent | Set to `false` in bundle app envs |
| `LOCAL_DEV_USER_ID` | Local fallback user id | Manual |
| `DATABASE_URL` | Canonical DB URL override | Manual |
| `PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD` | Canonical PG-style DB settings | Manual |
| `LAKEBASE_HOST/PORT/DB/USER/PASSWORD` | Backward-compatible DB fallback | Manual |
| `SERVING_ENDPOINT_NAME` | Serving endpoint name | Yes (`valueFrom: serving-endpoint`) |
| `JOB_ID` | Job ID for background tasks | Yes (`valueFrom: app-job`) |
| `VOLUME_ROOT` | UC volume path | Yes (`valueFrom: uc-volume`) |
| `OPENAI_KEY` | OpenAI API key | Yes (`valueFrom: openai-key`) |
| `LAKEBASE_PASSWORD` | Database password | Yes (`valueFrom: lakebase-password`) |
| `KNOWLEDGE_ASSISTANT_ENDPOINT` | Knowledge Assistant endpoint name | Yes (`valueFrom: knowledge-assistant`) |
| `ENVIRONMENT` | Runtime environment label | Set in app_config env |
| `LOG_LEVEL` | Python logging level | Set in app_config env |
| `ENABLE_OBO` | On-behalf-of user mode | Set in app_config env |
| `VECTOR_SEARCH_ENDPOINT_NAME` | Vector search endpoint | Manual |
| `VECTOR_SEARCH_INDEX_NAME` | Vector search index | Manual |

See `env.example` for the full list of configuration variables.

## Security

### Authentication

Databricks Apps authenticates users and forwards identity via HTTP headers:

| Header | Maps to |
|--------|---------|
| `X-Forwarded-User` | `user.id` (primary key) |
| `X-Forwarded-Email` | `user.email` |
| `X-Forwarded-Preferred-Username` | `user.preferred_username` |

For local development you have two options:

- keep `ENABLE_LOCAL_DEV_AUTH_FALLBACK=true` and use the fallback user from `LOCAL_DEV_USER_ID`
- disable the fallback and pass headers manually

```bash
curl http://localhost:8000/api/projects \
  -H "X-Forwarded-User: me@example.com" \
  -H "X-Forwarded-Email: me@example.com"
```

### Rate limiting

Expensive endpoints are rate-limited using an in-memory fixed-window strategy. Disable with `RATE_LIMIT_ENABLED=false` for development.

### Request limits

| Content type | Default limit | Setting |
|-------------|---------------|---------|
| JSON / other | 1 MiB | `MAX_REQUEST_BODY_BYTES` |
| Multipart (uploads) | 10 MiB | `MAX_UPLOAD_BYTES` |

### Security headers

The application applies OWASP-recommended HTTP security headers (HSTS, content type, frame and referrer policies) via the [`secure`](https://github.com/TypeError/secure) library.

### Dependency management

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. `requirements.txt` is generated — do not edit manually:

```bash
uv lock
uv export --no-hashes --no-editable --format=requirements.txt > requirements.txt
```

CI verifies that `requirements.txt` matches the lockfile on every PR.

## Health and Readiness

- `GET /api/health/live` and `GET /health/live` return lightweight process liveness
- `GET /api/health/ready` and `GET /health/ready` return **core readiness only** (database required)
- `GET /api/health/integrations` and `GET /health/integrations` return Databricks integration status for `workspace`, `ai`, and `vector_search`
- `GET /healthcheck` and `GET /databasehealthcheck` remain as compatibility aliases

In offline local mode:

- liveness returns `200`
- readiness returns `200` once the database is reachable
- integrations returns `200` with `status=degraded` and per-integration `disabled` entries

Databricks-dependent routes now fail at request time with clear `503` responses when integrations are disabled or unavailable, instead of breaking startup or unrelated routes.

## Observability

The application ships with OpenTelemetry instrumentation. When deployed to Databricks Apps with telemetry enabled, traces, metrics, and correlated logs are exported to Unity Catalog system tables.

| Signal | Source |
|--------|--------|
| HTTP request spans | Auto-instrumented (FastAPI, httpx, requests) |
| SQL spans | Auto-instrumented (SQLAlchemy) |
| Dependency spans | Manual spans around Serving, Jobs, AI Gateway, Vector Search, Genie |
| Log correlation | Every log line includes `trace_id`, `span_id`, `request_id` |

### Enabling telemetry

1. Open your Databricks Apps instance in the workspace UI
2. Go to **Settings > Telemetry** and toggle on
3. Select a Unity Catalog catalog and schema for telemetry tables

### Local tracing (optional)

```bash
docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
OTEL_SERVICE_NAME=fastapi-starter-local \
opentelemetry-instrument uvicorn main:app --reload
```

## Caching

- **Memory backend** (default) for local development
- **Redis backend** for production — set `CACHE_BACKEND=redis` and configure `CACHE_REDIS_*` variables
- Reads use cache-aside pattern; writes explicitly invalidate
- Cache failures are swallowed and logged; they never break correctness

## SSE Demo

A simple Server-Sent Events demo endpoint is available at `GET /api/stream/sse`:

```bash
curl -N http://localhost:8000/api/stream/sse
# event: message
# data: chunk-0
# ...
# event: done
# data: complete
```

Accepts an optional `count` parameter (1-20, default 3).

## Troubleshooting

### CLI version mismatch

```
Error: This bundle requires Databricks CLI >= 0.283.0
```

Upgrade: `databricks --version` to check, then reinstall via `databricks/setup-cli@main` or your package manager.

### Missing secret scope values

```
Error: Secret not found: starter_scope_dev/LAKEBASE_PASSWORD
```

Populate secrets after bundle deploy:

```bash
databricks secrets put-secret starter_scope_dev LAKEBASE_PASSWORD
databricks secrets put-secret starter_scope_dev OPENAI_KEY
```

### OIDC federation policy mismatch

If GitHub Actions deploy fails with auth errors when using OIDC, verify:
- The service principal's federation policy matches the repository and branch
- `id-token: write` permission is set in the workflow
- `DATABRICKS_CLIENT_ID` matches the service principal

### App returns 502

The app must bind to `0.0.0.0` and use the `DATABRICKS_APP_PORT` environment variable. The `run_app.py` launcher handles this automatically. If you see 502 errors, check:
- `run_app.py` is the entry point in your app config
- The app starts without import errors (check `/logz` in the Apps UI)

### Bundle validation fails

```bash
databricks bundle validate -t dev
```

Common causes:
- Missing or invalid resource references in `resources/*.yml`
- Unsupported resource types for your CLI version
- YAML syntax errors in complex variables
