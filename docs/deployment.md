# Deployment

One command provisions and starts everything for a target:

```bash
databricks bundle validate --strict -t dev --profile "$DATABRICKS_CONFIG_PROFILE"
databricks bundle deploy -t dev --profile "$DATABRICKS_CONFIG_PROFILE"
```

## What the deploy does, in order

1. `prebuild` hook: `npm ci` and `npm run build` in `frontend/`; the output lands in `backend/public`, which
   the bundle syncs although it is gitignored.
2. Resources under `resources/` are created or updated: Unity Catalog schema and volume, the Lakebase
   Autoscaling project, role and database, the AI Search endpoint, the experiments (with traces stored in Unity
   Catalog), the jobs, the secret scopes, and finally the app with its bindings.
3. The app is deployed from `backend/` (built from `pyproject.toml` and `uv.lock`) and started
   (`lifecycle.started`). Migrations run at every start under an advisory lock in the app-owned schema.
4. `postdeploy` hook: `scripts/postdeploy_grants.sh` grants `USE_SCHEMA` and `SELECT` on the bundle schema to
   the app's service principal. It receives `${workspace.profile}` from the bundle and fails the deploy if the app
   has no service principal yet.

The deploy needs the Databricks CLI (1.16 or newer), Node (see `.nvmrc`), `uv` and `jq`. The supervisor and
embedding models are pay-per-token Foundation Model endpoints that must exist in the workspace; the bundle binds
them but does not create them.

## Targets

| Target    | Mode          | What differs                                                                                                                                                                           |
| --------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dev`     | `development` | schema, job and experiment names prefixed per developer; docs and showcase routes on; ingestion trigger unpaused explicitly; Lakebase project purged on destroy; app open to all users |
| `staging` | default       | own schema `starter_rag_stg`; smaller Lakebase endpoint that suspends; no destroy protection                                                                                           |
| `prod`    | default       | on-behalf-of on (`forward_user_access_token`, `user_api_scopes`); Lakebase 1 to 4 CU, never suspends; `prevent_destroy` on the project                                                 |

App names, the Lakebase project id, the AI Search endpoint and the secret scopes are shared per target, so two
developers deploying `dev` share them. The bundle root is the deploying identity's home folder.

## First-deploy troubleshooting

| Symptom                                                                    | Cause and fix                                                                                           |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `lifecycle.started is only supported in direct deployment mode`            | an older deployment used the Terraform engine: `databricks bundle deployment migrate -t dev` once       |
| `Must specify environment variable source using either value or valueFrom` | an env entry has an empty value; move optional entries to a target block                                |
| `Found N recommendations` on validate                                      | a file holds more than one resource; keep one resource per `<key>.<type>.yml` (CI validates `--strict`) |
| `INTERNAL_ERROR: Failed to grant permissions for SP ... deadline exceeded` | transient on the Lakebase side; re-run the deploy                                                       |
| `postdeploy: app ... has no service principal`                             | the app was created but has no principal yet; re-run `bash scripts/postdeploy_grants.sh <target>`       |
| `ai: Unavailable` in `/api/health`                                         | the supervisor model endpoint is missing or not queryable by the app; check `supervisor_model`          |
| `Index not created yet` in `/api/health`                                   | expected before the first ingestion run; upload a document or run `rag_ingestion_job`                   |
| Traces missing in the experiment                                           | `MLFLOW_TRACE_ENABLE_OTLP_DUAL_EXPORT` must stay `true` while telemetry export is on                    |
| `not ready to sync` from the ingestion job                                 | a freshly created index is still provisioning; the job waits and tolerates this                         |
| `trace_location` rejected on an existing experiment                        | the field is immutable; use a new experiment name                                                       |

## Verify a deploy

```bash
databricks apps get fastapi-starter-dev --profile "$DATABRICKS_CONFIG_PROFILE" -o json | jq '{state: .app_status.state, compute: .compute_status.state}'
TOKEN=$(databricks auth token --profile "$DATABRICKS_CONFIG_PROFILE" | jq -r .access_token)
curl -s -H "Authorization: Bearer $TOKEN" "$APP_URL/api/health"            # version == deployed commit
curl -s -H "Authorization: Bearer $TOKEN" -X POST "$APP_URL/api/agents/supervisor/invocations" \
  -H 'Content-Type: application/json' -d '{"input":[{"role":"user","content":"Say hello in five words."}]}'
```

The invocation reply carries the MLflow trace id; the trace sits in the app experiment and in the
`app_mlflow_*` tables of the bundle schema. Application logs: `databricks apps logs fastapi-starter-dev`.
