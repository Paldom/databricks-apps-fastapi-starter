#!/usr/bin/env bash
# Bundle postdeploy hook: the app's service principal reads the AI Search index and writes
# MLflow traces into the bundle schema. Both live in Unity Catalog, where an app binding
# cannot express table privileges, so the deployer grants them after every deploy.
# Usage: postdeploy_grants.sh <bundle target>   (reads names from `bundle summary`)
set -euo pipefail
TARGET=$1
SUMMARY=$(databricks bundle summary -t "$TARGET" -o json)
APP=$(echo "$SUMMARY" | jq -r '.resources.apps.fastapi_app.name')
SCHEMA=$(echo "$SUMMARY" | jq -r '"\(.resources.schemas.rag_schema.catalog_name).\(.resources.schemas.rag_schema.name)"')
SP=$(databricks apps get "$APP" -o json | jq -r '.service_principal_client_id // empty')
if [ -z "$SP" ]; then
  echo "postdeploy: app $APP has no service principal yet; skipping grants" >&2
  exit 0
fi
databricks grants update SCHEMA "$SCHEMA" --json "{\"changes\": [{\"principal\": \"$SP\", \"add\": [\"USE_SCHEMA\", \"SELECT\", \"MODIFY\"]}]}" > /dev/null
echo "postdeploy: granted USE_SCHEMA, SELECT, MODIFY on $SCHEMA to the service principal of $APP"
