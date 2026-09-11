#!/usr/bin/env bash
# Bundle postdeploy hook. The app's service principal queries the AI Search index, a table that
# exists only after the first ingestion run, so it cannot be an app binding (the trace tables are).
# The deployer grants USE_SCHEMA + SELECT on the bundle schema after every deploy.
# Usage: postdeploy_grants.sh <bundle target> [profile]   (the bundle passes ${workspace.profile})
set -euo pipefail
TARGET=$1
PROFILE=${2:-${DATABRICKS_CONFIG_PROFILE:-}}
cli() { databricks "$@" ${PROFILE:+--profile "$PROFILE"}; }

SUMMARY=$(cli bundle summary -t "$TARGET" -o json)
APP=$(echo "$SUMMARY" | jq -r '.resources.apps.fastapi_app.name')
CATALOG=$(echo "$SUMMARY" | jq -r '.resources.schemas.rag_schema.catalog_name')
SCHEMA=$(echo "$SUMMARY" | jq -r '.resources.schemas.rag_schema.name')
SP=$(cli apps get "$APP" -o json | jq -r '.service_principal_client_id // empty')
if [ -z "$SP" ]; then
  echo "postdeploy: app $APP has no service principal; re-run: bash scripts/postdeploy_grants.sh $TARGET" >&2
  exit 1
fi
cli grants update SCHEMA "$CATALOG.$SCHEMA" --json "{\"changes\": [{\"principal\": \"$SP\", \"add\": [\"USE_SCHEMA\", \"SELECT\"]}]}" > /dev/null
echo "postdeploy: granted USE_SCHEMA, SELECT on $CATALOG.$SCHEMA to the service principal of $APP"
