#!/usr/bin/env bash
# Bundle postdeploy hook. The app's service principal queries the AI Search index and writes
# MLflow traces into the bundle schema; both are Unity Catalog privileges that an app binding
# cannot express, so the deployer grants them after every deploy:
#   USE_SCHEMA + SELECT on the schema (index queries), MODIFY on the app's trace tables only.
# Usage: postdeploy_grants.sh <bundle target> [profile]   (the bundle passes ${workspace.profile})
set -euo pipefail
TARGET=$1
PROFILE=${2:-${DATABRICKS_CONFIG_PROFILE:-}}
cli() { databricks "$@" ${PROFILE:+--profile "$PROFILE"}; }

SUMMARY=$(cli bundle summary -t "$TARGET" -o json)
APP=$(echo "$SUMMARY" | jq -r '.resources.apps.fastapi_app.name')
CATALOG=$(echo "$SUMMARY" | jq -r '.resources.schemas.rag_schema.catalog_name')
SCHEMA=$(echo "$SUMMARY" | jq -r '.resources.schemas.rag_schema.name')
PREFIX=$(echo "$SUMMARY" | jq -r '.resources.experiments.app_experiment.trace_location.uc_trace_location.table_prefix // empty')
SP=$(cli apps get "$APP" -o json | jq -r '.service_principal_client_id // empty')
if [ -z "$SP" ]; then
  echo "postdeploy: app $APP has no service principal; re-run: bash scripts/postdeploy_grants.sh $TARGET" >&2
  exit 1
fi
grant() { cli grants update "$1" "$2" --json "{\"changes\": [{\"principal\": \"$SP\", \"add\": [$3]}]}" > /dev/null; }
grant SCHEMA "$CATALOG.$SCHEMA" '"USE_SCHEMA", "SELECT"'
TABLES=$(cli tables list "$CATALOG" "$SCHEMA" -o json | jq -r --arg p "${PREFIX:-__none__}_" '(. // []) | .[] | select(.table_type == "MANAGED" and (.name | startswith($p))) | .name')
for table in $TABLES; do grant TABLE "$CATALOG.$SCHEMA.$table" '"MODIFY"'; done
echo "postdeploy: granted USE_SCHEMA, SELECT on $CATALOG.$SCHEMA and MODIFY on ${PREFIX}_* tables to the service principal of $APP"
