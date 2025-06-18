# databricks-apps-fastapi-starter
Sample FastAPI application to showcase how to leverage Databricks services.

This repository serves as a Databricks **Apps** sample.  It demonstrates how a
FastAPI backend can call various Databricks capabilities including jobs,
serving endpoints, the AI Gateway, Vector Search and Lakebase.

## Quickstart

1. [Sign up for a free Databricks account](https://www.databricks.com/learn/free-edition).
2. In the workspace UI open your user icon in the top‑right corner,
   choose **Previews** and enable **Lakebase (OLT)**.


The demo controller (`controllers/demo.py`) exercises several Databricks services:

- **Serving Endpoint** – queries an MLflow model registered and deployed via the asset bundle.
- **Databricks Jobs** – triggers a job defined in `databricks.yml` and returns its output.
- **AI Gateway** – obtains embeddings used for vector storage.
- **Vector Search** – stores and searches embeddings in a vector search index.

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

Create a `.env` file based on `env.example`:

```bash
cp env.example .env
```

Edit `.env` or set the variables directly in the environment.  When
deploying on Databricks, you can also store these values in your secret
scope so that the application loads them automatically when environment
variables are absent.

## Security

The application applies common HTTP security headers using the
[`secure`](https://github.com/TypeError/secure) library. These headers
include HSTS, content type, frame and referrer policies in line with
OWASP recommendations.

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
