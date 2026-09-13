# Lakebase

The app's state lives in a **Lakebase Autoscaling** project declared by the bundle:
`resources/app_db.postgres_project.yml` (Postgres 17, compute settings per target), `app_role.postgres_role.yml`
and `main_database.postgres_database.yml`. The app binds the production branch and the database
(`postgres` binding, `CAN_CONNECT_AND_CREATE`).

## Connection

The Apps runtime injects `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGSSLMODE` and `PGAPPNAME`; there is no
`PGPASSWORD`. The SQLAlchemy engine mints the app's OAuth token in a `do_connect` hook for every new connection
(tokens expire after an hour), recycles pooled connections before that and pings them before use
(`backend/app/core/db/engine.py`). Locally, `backend/env.example` points at the Docker Postgres from
`make dev-db`.

## The app-owned schema

The app's service principal may connect and create but cannot write to `public`, so the app owns its own schema
(`DB_SCHEMA`, default `app`): migrations create it, the engine sets `search_path` to it, and Alembic keeps its
version table there. One migration, `backend/alembic/versions/0001_initial.py`, creates the whole schema; new
migrations come from `make migrate-new MIGRATION_MESSAGE="..."` and run at every app start under a Postgres
advisory lock with a lock timeout, so several app instances never race.

## Sizing

| Target  | Endpoint                              |
| ------- | ------------------------------------- |
| dev     | 0.5 to 2 CU, suspends after 5 minutes |
| staging | same as dev                           |
| prod    | 1 to 4 CU, never suspends             |

The values are the `lakebase_endpoint_settings` variable (a complex variable overridden per target). A suspended
endpoint wakes on the first connection; the app tolerates that with its pool settings.

## Branches for pull requests

Branches are copy-on-write and appear in about a second regardless of size. Declare one as a bundle resource
(`postgres_branches`, with a TTL) in a scratch target, point the app at it through the `postgres` binding and run
migrations and tests against production-shaped data; the TTL reaps it. Branches are one-way (no merge back) and
authenticate with OAuth only.

## Local inspection

```bash
databricks postgres list-branches projects/fastapi-starter-dev --profile "$DATABRICKS_CONFIG_PROFILE"
databricks psql --project fastapi-starter-dev --profile "$DATABRICKS_CONFIG_PROFILE" -- -c '\dt app.*'
```

The project creator has `databricks_superuser`; the app's tables are readable that way without touching the
app's identity.

## Resetting a development database

The app's service principal owns the schema, so the project owner cannot drop it (`must be owner of schema`),
and `databricks_superuser` membership does not change that. To start over in `dev`, delete the database and let
the next deploy recreate it (the bundle owns `postgres_databases.main_database`; the app binding re-grants
`CAN_CONNECT_AND_CREATE` and the migration rebuilds the schema):

```bash
databricks postgres delete-database projects/fastapi-starter-dev/branches/production/databases/app --profile "$DATABRICKS_CONFIG_PROFILE"
databricks bundle deploy -t dev --profile "$DATABRICKS_CONFIG_PROFILE"
```

A database whose `alembic_version` names a revision that no longer exists fails the app at start with
`Can't locate revision`; this reset is the fix in `dev`. Never do this on a database with data you want.
