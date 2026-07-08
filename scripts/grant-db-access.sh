#!/usr/bin/env bash
# One-time post-first-deploy step: give the app's service principal a schema
# it owns inside the Lakebase database.
#
# Why: Lakebase runs Postgres 15+, where non-owners cannot CREATE in the
# `public` schema, and the app resource binding grants CONNECT only. Alembic
# migrations and the LangGraph checkpointer both create tables, so the app
# uses its own schema (Settings.pg_app_schema, default "starter") — which the
# instance owner must create once, owned by the app's service principal.
#
# Usage: scripts/grant-db-access.sh [-p PROFILE] [-a APP_NAME] [-i INSTANCE] [-d DATABASE] [-s SCHEMA]
set -euo pipefail

PROFILE="${DATABRICKS_CONFIG_PROFILE:-DEFAULT}"
APP_NAME="fastapi-starter"
INSTANCE=""
DATABASE="starter_app"
SCHEMA="starter"
while getopts "p:a:i:d:s:" opt; do
  case $opt in
    p) PROFILE="$OPTARG" ;;
    a) APP_NAME="$OPTARG" ;;
    i) INSTANCE="$OPTARG" ;;
    d) DATABASE="$OPTARG" ;;
    s) SCHEMA="$OPTARG" ;;
    *) echo "usage: $0 [-p profile] [-a app] [-i instance] [-d database] [-s schema]" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }

if [ -z "$INSTANCE" ]; then
  INSTANCE=$(databricks database list-database-instances -p "$PROFILE" -o json \
    | python3 -c 'import json,sys; xs=json.load(sys.stdin); print(next(i["name"] for i in xs if i["name"].startswith("starter-oltp")))')
fi
say "Instance: $INSTANCE · database: $DATABASE · schema: $SCHEMA"

SP=$(databricks apps get "$APP_NAME" -p "$PROFILE" -o json \
  | python3 -c 'import json,sys; a=json.load(sys.stdin); print(a["service_principal_client_id"])')
DNS=$(databricks database get-database-instance "$INSTANCE" -p "$PROFILE" -o json \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["read_write_dns"])')
ME=$(databricks current-user me -p "$PROFILE" -o json \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["userName"])')
TOKEN=$(databricks database generate-database-credential \
  --json "{\"instance_names\":[\"$INSTANCE\"]}" -p "$PROFILE" -o json \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')

say "Creating database \"$DATABASE\" and schema \"$SCHEMA\" owned by app SP $SP"
cd "$(dirname "$0")/../backend"
PGPASSWORD="$TOKEN" uv run python - "$DNS" "$DATABASE" "$ME" "$SP" "$SCHEMA" <<'PY'
import os
import sys

import psycopg

dns, database, me, sp, schema = sys.argv[1:6]

def connect(dbname):
    return psycopg.connect(
        host=dns,
        dbname=dbname,
        user=me,
        password=os.environ["PGPASSWORD"],
        sslmode="require",
        autocommit=True,
    )

# CREATE DATABASE has no IF NOT EXISTS; go through the instance's default db.
with connect("databricks_postgres") as admin, admin.cursor() as cur:
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
    if cur.fetchone() is None:
        cur.execute(f'CREATE DATABASE "{database}"')
        print(f"database {database!r} created")

conn = connect(database)
with conn.cursor() as cur:
    cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}" AUTHORIZATION "{sp}"')
    cur.execute(
        "SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname = %s",
        (schema,),
    )
    print(f"schema {schema!r} owner:", cur.fetchone()[0])
conn.close()
PY

say "Done. Restart the app to pick it up:"
echo "  databricks bundle run -t dev -p $PROFILE fastapi_app"
