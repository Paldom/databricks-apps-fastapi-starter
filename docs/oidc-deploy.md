# GitHub OIDC deploys (no long-lived secrets)

`deploy.yml` ships with service-principal client-secret auth for portability.
The hardened setup is workload identity federation:

1. Create a federation policy on the service principal:
   ```bash
   databricks account service-principal-federation-policy create <SP_ID> --json '{
     "oidc_policy": {
       "issuer": "https://token.actions.githubusercontent.com",
       "audiences": ["<org>/<repo>"],
       "subject": "repo:<org>/<repo>:environment:production"
     }
   }'
   ```
2. Workflow changes: add `permissions: id-token: write`, drop the secret env
   vars, and set `DATABRICKS_AUTH_TYPE: github-oidc`,
   `DATABRICKS_CLIENT_ID: <sp-application-id>`, `DATABRICKS_HOST`.
3. The Databricks CLI exchanges the GitHub job's OIDC token automatically —
   nothing to rotate, nothing to leak.
