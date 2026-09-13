# GitHub deploys with workload identity federation

`.github/workflows/deploy.yml` deploys without any stored secret: the job requests an OIDC token
(`permissions: id-token: write`) and the Databricks CLI exchanges it for a workspace token
(`DATABRICKS_AUTH_TYPE: github-oidc`). Two repository variables are needed: `DATABRICKS_HOST` and
`DATABRICKS_CLIENT_ID`, the application id of a service principal with a federation policy:

```bash
databricks account service-principal-federation-policy create <SP_ID> --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["<org>/<repo>"],
    "subject": "repo:<org>/<repo>:environment:dev"
  }
}'
```

One policy per GitHub environment (`dev`, `staging`, `prod`), because the `subject` names the environment. The
service principal needs the workspace permissions the bundle exercises: create apps, jobs, experiments, secret
scopes, Lakebase projects and AI Search endpoints, plus `USE CATALOG` and `CREATE SCHEMA` on the catalog.

The workflow deploys `dev` on every push to `main` and `staging` or `prod` on manual dispatch inside the matching
GitHub environment, then polls `/api/health` until the app serves the pushed commit. The same identity runs the
`postdeploy` hook, so it must be allowed to grant on the bundle schema.
