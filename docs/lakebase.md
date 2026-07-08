# Lakebase

## The app schema (`starter`)

Lakebase runs Postgres 15+, where non-owners cannot `CREATE` in the `public`
schema. The app therefore keeps all its tables (Alembic models **and**
LangGraph checkpoints) in its own schema (`Settings.pg_app_schema`, default
`starter`), wired through the engine's `search_path`, Alembic, and the
checkpointer. Because the `database` binding grants `CAN_CONNECT_AND_CREATE`
(Postgres `CREATE` on the database), Alembic creates the schema itself on
first startup — no owner step needed. If your binding grants CONNECT only,
create the schema once as the instance owner:

```bash
make grant-db-access PROFILE=<profile>   # creates the DB + SP-owned schema
```

## Durable chat memory (LangGraph checkpointer)

`LANGGRAPH_MEMORY_BACKEND=lakebase` (the deployed default) stores LangGraph
checkpoints in Lakebase via `AsyncPostgresSaver` on a psycopg connection pool.
Every new connection authenticates with a freshly minted OAuth token (Lakebase
tokens expire hourly), mirroring the SQLAlchemy engine's token hook. If the
database is unreachable the app falls back to in-memory with a warning —
startup never crashes. Implementation: `backend/app/chat/memory.py`.

## Branching: per-PR ephemeral databases

Lakebase (Postgres) branches are zero-copy (copy-on-write) and create in ~1s
regardless of size — "git for databases".

```bash
# branch off the dev instance for a PR
databricks database create-database-branch <instance> --name pr-1234 --ttl 4h
# point the PR's app/test run at the branch (PG* env from the branch endpoint)
# run migrations + integration tests against real data, then let TTL reap it
```

Uses: schema-migration validation on production-shaped data, per-developer
sandboxes, agent-provisioned scratch DBs, point-in-time recovery as a branch.
Gotchas: one-way (no merge back), OAuth-only credentials, watch branch sprawl.
