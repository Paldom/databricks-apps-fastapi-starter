# GitHub deploys with workload identity federation

`.github/workflows/deploy.yml` deploys without any stored secret: the job requests an OIDC token
(`permissions: id-token: write`) and the Databricks SDK exchanges it for a workspace token
(`DATABRICKS_AUTH_TYPE: github-oidc`). Two repository variables are needed: `DATABRICKS_HOST` and
`DATABRICKS_CLIENT_ID`, the application id of a service principal that carries federation policies.

## Audience and subjects

The SDK requests the GitHub token with the workspace token endpoint as audience
(`https://<workspace-host>/oidc/v1/token`) unless `DATABRICKS_TOKEN_AUDIENCE` is set; the policy must name
the same value. The subject depends on the job: a job inside a GitHub environment presents
`repo:<org>/<repo>:environment:<name>`; the `bundle validate` job in `ci.yml` has no environment and presents
`repo:<org>/<repo>:pull_request` or `repo:<org>/<repo>:ref:refs/heads/main`. One policy per subject:

```bash
databricks account service-principal-federation-policy create <SP_ID> --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["https://<workspace-host>/oidc/v1/token"],
    "subject": "repo:<org>/<repo>:environment:dev"
  }
}'
```

Repeat for `staging`, `prod`, `pull_request` and `ref:refs/heads/main`. The service principal needs the
workspace permissions the bundle exercises: create apps, jobs, experiments, secret scopes, Lakebase projects and
AI Search endpoints, plus `USE CATALOG` and `CREATE SCHEMA` on the catalog; the `postdeploy` hook runs as
the same identity, so it must be allowed to grant on the bundle schema.

## What the workflow does

`deploy.yml` deploys `dev` on every push to `main` and `staging` or `prod` on manual dispatch inside the
matching GitHub environment, then polls `/api/health` until the app serves the pushed commit.
