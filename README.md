# databricks-apps-fastapi-starter

[![Snyk Vulnerabilities](https://snyk.io/test/github/Paldom/databricks-apps-fastapi-starter/badge.svg)](https://snyk.io/test/github/Paldom/databricks-apps-fastapi-starter)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Paldom_databricks-apps-fastapi-starter&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=Paldom_databricks-apps-fastapi-starter)
![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/Paldom/databricks-apps-fastapi-starter?utm_source=oss&utm_medium=github&utm_campaign=Paldom%2Fdatabricks-apps-fastapi-starter&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)

[![Databricks](https://img.shields.io/badge/Databricks-Apps-red.svg)](https://docs.databricks.com/en/dev-tools/databricks-apps/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Sample FastAPI application to showcase how to leverage Databricks services.

A production-ready FastAPI template for building data and AI applications on **Databricks Apps**, featuring built-in authentication, database connectivity, and deployment automation. It demonstrates how a FastAPI backend can call various Databricks capabilities including Jobs, Serving endpoints, Delta tables & Volumes, AI Gateway, Vector Search and Lakebase.

## Why This Starter?

- **Zero to Production**: Deploy a secure API in minutes, sample CI/CD, IaC.
- **Built for Databricks**: Native integration with Lakebase, Vector Search Index, Unity Catalog, Model Serving.
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

## Databricks Services

The integration controllers under `app/api/integrations/` exercise several Databricks services:

- **Serving Endpoint** -- queries an MLflow model that can scale seamlessly with no latency. Recommended for complex but critical tasks.
- **Databricks Jobs** -- triggers a job and returns its output. Recommended for heavy duty background tasks, like media conversion, parsing, where latency is not a problem, but a custom cluster can be useful.
- **AI Gateway** -- gateway for embeddings or foundation model's AI query.
- **Vector Search** -- stores and searches embeddings in a vector search index.
- **Delta Table** -- read and persists data in a Unity Catalog Delta table.
- **Volume** -- reads and writes files in a Unity Catalog's Volume.
- **Genie** -- ask natural language questions about your data using the Conversation API.

### Genie conversation API

Databricks Genie lets applications query data using natural language.
The demo exposes `/api/v1/genie/{space_id}/ask` to start a conversation and
`/api/v1/genie/{space_id}/{conversation_id}/ask` for follow-up questions.
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
    health_controller.py          # /health/live, /health/ready
    user_controller.py            # /userInfo
    todo_controller.py            # /todos CRUD
    integrations/                 # Demo integration controllers (thin HTTP layer)
  services/
    todo_service.py               # Todo business logic + UoW transaction scopes
    integrations/                 # Integration orchestration services
  repositories/
    todo_repository.py            # SQLAlchemy Todo persistence (flush only)
    user_repository.py            # User upsert (flush only)
    lakebase_demo_repository.py   # Lakebase demo via SQLAlchemy text()
    delta_todo_repository.py      # Delta table access via SQL adapter
  models/
    __init__.py                   # Model registry (imports all ORM models)
    base.py                       # Re-exports from core.db.base
    todo_model.py                 # Todo ORM model
    user_model.py                 # AppUser ORM model (users table)
    chat_session_model.py         # ChatSession ORM model
    message_model.py              # Message ORM model
    file_record_model.py          # FileRecord ORM model
    todo_dto.py                   # Pydantic DTOs + mapper
    user_dto.py                   # CurrentUser, UserInfo
    integrations/                 # Integration request/response DTOs
  core/
    bootstrap.py                  # Lifespan (startup/shutdown) — no schema creation
    config.py                     # Pydantic Settings + Databricks secrets
    deps.py                       # DI factory functions (adapters, services, repos)
    errors.py                     # AppError hierarchy
    logging.py                    # Logging setup
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
    user_info.py                  # Auth header extraction + user upsert
    workspace_client.py           # OBO WorkspaceClient
    security_headers.py           # OWASP security headers
```

### Dependency Flow

```
Controller -> Service -> Repository / Adapter -> Shared deps (app.state)
```

- **Controllers** are thin: route definition, input validation, HTTP response construction only.
- **Services** own business logic and adapter orchestration.
- **Repositories** handle persistence (SQLAlchemy) — flush only, never commit.
- **Adapters** (`app/core/databricks/`) wrap low-level SDK calls with error mapping, timeouts, and thread bridging.

### Router Registry

`app/api/api.py` is the canonical router registry. All versioned routes are served under `/api/v1` (canonical) and `/v1` (legacy, excluded from OpenAPI schema). Health checks remain unversioned at `/health/*`.

### Error Handling

Adapters raise typed `AppError` subclasses (e.g., `ServingEndpointError`, `ConfigurationError`). A global exception handler in `app/main.py` converts these to appropriate HTTP responses. Controllers do not need try/except blocks for adapter errors.

### DI and Testing

All runtime resources (engine, session_factory, ai_client, vector_index) are stored on `app.state` during bootstrap. DI factory functions in `app/core/deps.py` read from `request.app.state`, making tests simple:
- **Controller tests**: mock services via `dependency_overrides`
- **Service tests**: construct with mock adapters/repos (no FastAPI needed)
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
  used by both the serving and AI Gateway demo endpoints
- `JOB_ID`
- `LAKEBASE_HOST`
- `LAKEBASE_PORT`
- `LAKEBASE_DB`
- `LAKEBASE_USER`
- `LAKEBASE_PASSWORD`
- `ENVIRONMENT` - set to `production` to disable the OpenAPI documentation
- `LOG_LEVEL` - Python logging level used by the application
- `VOLUME_ROOT` - root UC volume path for the demo file endpoints
- `ENABLE_OBO` - set to `true` to accept `X-Forwarded-Access-Token`

Create a `.env` file based on `env.example`:

```bash
cp env.example .env
```

Edit `.env` or set the variables directly in the environment.  When
deploying on Databricks, you can also store these values in your secret
scope so that the application loads them automatically when environment
variables are absent.

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

## Deployment

The repository includes `.github/workflows/deploy.yml` which deploys the app
to Databricks using the Databricks CLI. Configure the required secrets and push
to the `main` branch to trigger a deployment.

Set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` secrets before first run.

### Migration-first startup

The application does **not** create database tables at runtime. Alembic
migrations must be applied before the server starts. The `app.yaml` entry
point runs `alembic upgrade head` automatically before launching uvicorn.

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
