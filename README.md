# databricks-apps-fastapi-starter

[![Snyk Vulnerabilities](https://snyk.io/test/github/Paldom/databricks-apps-fastapi-starter/badge.svg)](https://snyk.io/test/github/Paldom/databricks-apps-fastapi-starter)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Paldom_databricks-apps-fastapi-starter&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=Paldom_databricks-apps-fastapi-starter)
[![CodeRabbit AI](https://img.shields.io/badge/CodeRabbit-AI%20Code%20Review-orange?logo=rabbitmq&logoColor=white)](https://github.com/marketplace/coderabbitai)

Sample FastAPI application to showcase how to leverage Databricks services.

This repository serves as a Databricks **Apps** sample.  It demonstrates how a
FastAPI backend can call various Databricks capabilities including jobs,
serving endpoints, the AI Gateway, Vector Search and Lakebase.

## Quickstart

1. [Sign up for a free Databricks account](https://www.databricks.com/learn/free-edition).
2. In the workspace UI open your user icon in the top‑right corner,
   choose **Previews** and enable **Lakebase (OLTP)**.
3. Still in the **Previews** menu, enable **User authorization for Databricks Apps**. Optinally, you may also need to enable **On-behalf-of-user authentication**

The demo controller (`controllers/demo.py`) exercises several Databricks services:

- **Serving Endpoint** – queries an MLflow model registered and deployed via the asset bundle.
- **Databricks Jobs** – triggers a job defined in `databricks.yml` and returns its output.
- **AI Gateway** – obtains embeddings used for vector storage.
- **Vector Search** – stores and searches embeddings in a vector search index.
- **Delta Table** – persists todo items in a Unity Catalog Delta table.
- **Volume** – reads and writes files in a Unity Catalog volume.
- **Genie** – ask natural language questions about your data using the
  Conversation API.

### Genie conversation API

Databricks Genie lets applications query data using natural language.
The demo exposes `/v1/genie/{space_id}/ask` to start a conversation and
`/v1/genie/{space_id}/{conversation_id}/ask` for follow-up questions.
Databricks Apps automatically provide the host URL and token used by these
endpoints.

Infrastructure for these services is described using a Databricks Asset Bundle
(`databricks.yml`).  The `notebooks/serving` directory defines the simple
MLflow model that backs the serving endpoint and `notebooks/jobs` contains the
notebook executed by the job resource.

## Setup

Create a virtual environment and install dependencies:
```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e .
uv lock
uv export --format=requirements.txt > requirements.txt
uvicorn main:app --reload
```

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

The project uses [Alembic](https://alembic.sqlalchemy.org/) for schema
migrations. Ensure `DATABASE_URL` is set in your environment (see
`env.example`).

Create a new migration:

```bash
alembic revision --autogenerate -m "my change"
```

Apply pending migrations:

```bash
alembic upgrade head
```

## Structure

- **`core/database.py`** – PostgreSQL connection pool and dependency providers
- **`core/logging.py`** – application logging configuration
- **`controllers`** – FastAPI routers (`health`, `user`, `demo`, `todo`)
- **`modules/todo`** – example CRUD feature with SQLAlchemy models and services
Liveness and readiness endpoints are available at `/health/live` and `/health/ready`. The readiness check performs a lightweight AI Gateway call in addition to database checks.
## API versioning

All endpoints are served under the `/v1` prefix. Future versions of the API
will use different prefixes such as `/v2`.

## Configuration

The application reads its settings from environment variables using a
Pydantic `Settings` model defined in `config.py`.  When running locally you
can place these variables in a `.env` file which is automatically loaded.
If a value is not provided via the environment, the settings object will
attempt to look it up in Databricks secrets using the same key name.

Configuration keys:

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
`config.py` abstracts this difference. It calls
`w().secrets.get_secret(scope, key)`, decodes the value and returns the
decoded secret as a string.  It also exposes a low level `_db_secret`
function that returns `{"key": key, "value": decoded}` if you need the
pair directly.  Use `get_secret` whenever you need a secret at runtime:

```python
from config import get_secret

token = get_secret("MY_TOKEN", scope="starter_scope")
```

## Security

The application applies common HTTP security headers using the
[`secure`](https://github.com/TypeError/secure) library. These headers
include HSTS, content type, frame and referrer policies in line with
OWASP recommendations.

### Authentication

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

## Databricks Asset Bundle

To validate and deploy the infrastructure defined in `databricks.yml`, run:

```bash
databricks bundle validate
databricks bundle deploy -e dev
```

Use the Databricks CLI to provide values for the placeholder secrets:

```bash
databricks secrets put-secret starter_scope SERVING_ENDPOINT_NAME
databricks secrets put-secret starter_scope JOB_ID
databricks secrets put-secret starter_scope LAKEBASE_PASSWORD
databricks secrets put-secret starter_scope OPENAI_KEY
```
