# Security Hardening

This document describes the security controls in the Databricks Apps FastAPI
starter, their design rationale, and known limitations.

## Dependency management policy

| Artifact | Role |
|----------|------|
| `pyproject.toml` | Source of truth for direct dependencies |
| `uv.lock` | Source of truth for the resolved dependency graph |
| `requirements.txt` | **Generated** deployment artifact for Databricks Apps |

- Direct runtime dependencies use exact version pins unless a compatibility
  range is explicitly justified (e.g., OpenTelemetry, aiocache).
- Development tools may use ranges; the lockfile ensures reproducibility.
- Databricks-preinstalled libraries should only be overridden intentionally;
  use an exact version and document the reason.
- **Never hand-edit `requirements.txt`**. Regenerate with:
  ```bash
  uv lock
  uv export --no-hashes --no-editable --format=requirements.txt > requirements.txt
  ```
- CI verifies the file stays in sync via a diff step in the lint workflow.

## Security scanning

- **Snyk** (`.github/workflows/snyk-security.yml`) runs on PRs, pushes to
  main, and weekly. High/critical dependency vulnerabilities **fail the PR**.
  SARIF results upload to GitHub Code Scanning. `snyk monitor` on main
  provides ongoing drift monitoring.
- **Bandit** (`.github/workflows/lint.yml`) runs SAST on every PR.
- **Dependabot** (`.github/dependabot.yml`) proposes grouped weekly PRs
  for Python and GitHub Actions updates.
- **`.snyk`** ignores must be scoped to a specific vulnerability ID, file
  path, and expiry date. Broad wildcards are not permitted.

## Rate limiting

Expensive endpoints are rate-limited using [slowapi](https://github.com/laurentS/slowapi)
with an in-memory fixed-window strategy.

### Key strategy

The rate-limit key is derived in priority order:

1. Authenticated Databricks user ID (`request.state.user.id`)
2. Forwarded email or preferred username
3. `X-Real-Ip` header (set by the Databricks Apps proxy)
4. Client host (fallback)

### Default limits

| Endpoint | Limit |
|----------|-------|
| `POST /v1/serving` | 20/minute |
| `POST /v1/job` | 5/minute |
| `POST /v1/embed` | 20/minute |
| `POST /v1/vector/store` | 10/minute |
| `POST /v1/vector/query` | 20/minute |
| `POST /v1/genie/{space_id}/ask` | 5/minute |
| `POST /v1/genie/{space_id}/{conv}/ask` | 20/minute |
| `GET /health/ready` | 60/minute |
| `GET /health/deep` | 10/minute |

### Limitations

- **In-memory backend**: Rate counters are per-process. With multiple
  uvicorn workers, each worker tracks limits independently. For global
  rate limiting, use a Redis-backed limiter.
- Rate limiting can be disabled via `RATE_LIMIT_ENABLED=false`.

## Request body limits

A pure ASGI middleware enforces maximum request body sizes:

| Content type | Default limit | Setting |
|-------------|---------------|---------|
| JSON / other | 1 MiB | `MAX_REQUEST_BODY_BYTES` |
| Multipart (uploads) | 10 MiB | `MAX_UPLOAD_BYTES` |

The middleware short-circuits on `Content-Length` when present and also
enforces the cap while streaming the body.

The file upload endpoint (`POST /v1/uc/upload`) additionally reads files
in 8 KiB chunks and validates the total against `MAX_UPLOAD_BYTES`.

## Path validation

Volume paths (`/v1/uc/upload`, `/v1/uc/download`) are validated to prevent
path traversal:

- Empty, absolute, `..`, and null-byte paths are rejected with HTTP 400.
- Paths are normalized via `PurePosixPath`.

## Timeout strategy

All downstream calls have configurable timeouts:

| Setting | Default | Applies to |
|---------|---------|-----------|
| `SERVING_TIMEOUT_SECONDS` | 30 | Model serving queries |
| `JOB_TIMEOUT_SECONDS` | 120 | Databricks job runs |
| `VECTOR_TIMEOUT_SECONDS` | 30 | Vector search upsert/query |
| `GENIE_TIMEOUT_SECONDS` | 30 | Genie conversation API |
| `OPENAI_TIMEOUT_SECONDS` | 30 | AI Gateway (OpenAI client) |

Synchronous SDK calls run in a thread via `asyncio.to_thread()` and are
wrapped with `asyncio.wait_for()`. On timeout the async caller is
unblocked and an appropriate error is returned.

### Limitation

`asyncio.wait_for()` cancels the awaiting coroutine but the underlying
thread continues running (Python limitation). The async event loop is
protected from blocking, but the SDK thread may leak until it completes
naturally. This is an acceptable trade-off for a starter application.

## Health endpoints

| Endpoint | Cost | Purpose |
|----------|------|---------|
| `GET /healthcheck`, `GET /health/live` | Trivial | Liveness probe |
| `GET /health/ready` | Low | Readiness: checks client initialization only |
| `GET /health/deep` | Medium | Full dependency probes (cached) |

`/health/ready` verifies that runtime clients (database, AI, vector search)
were successfully initialized at startup. It does **not** make network calls.

`/health/deep` runs actual probes (database `SELECT 1`, AI embedding,
vector search describe) and caches results for `HEALTH_READY_CACHE_TTL`
seconds (default 30). It is rate-limited to 10 requests/minute.

## Uvicorn guardrails

The `app.yaml` command includes:

- `--limit-concurrency 100` — rejects requests beyond 100 simultaneous
  connections.
- `--timeout-keep-alive 5` — closes idle keep-alive connections after 5
  seconds.

## Error response format

All protective errors (400, 413, 429, 504) return consistent JSON:

```json
{
  "detail": "Human-readable description",
  "error_code": "machine_readable_code",
  "request_id": "..."
}
```

## Audit logging

Security events are logged with structured fields:

- `request_id`, `user_id`, `client_ip`, `route`, `event`
- OTel counters are incremented for each event type.

**Sensitive headers are never logged**: `Authorization`,
`X-Forwarded-Access-Token`.
