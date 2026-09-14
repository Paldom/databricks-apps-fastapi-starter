# The generated API client

The frontend never hand-writes request code for the backend. `make generate` runs three steps:

1. `backend/scripts/export_openapi.py` builds the FastAPI app and writes `backend/openapi.yaml`, including the
   NDJSON stream events (`ChatStreamEvent` with a discriminator over every event model).
2. `npm run api:gen` in `frontend/` runs **Orval** on that file (`frontend/orval.config.ts`): a TanStack Query
   client per tag under `src/shared/api/generated/<tag>/`, the models under `generated/models/`, and MSW handlers
   (`*.msw.ts`) built from the schema examples. Cursor-paginated lists get `useInfiniteQuery` hooks.
3. `backend/scripts/export_env_example.py` regenerates `backend/env.example` from `Settings`.

Commit all three outputs. CI regenerates and fails on any drift; a backend test asserts that `env.example` still
matches `Settings`, and another that the stream event mapping in the schema covers every event model.

## What is hand-written

The chat stream is consumed by `frontend/src/lib/assistant/chat-model-adapter.ts` (fetch + NDJSON parsing into
assistant-ui content parts) rather than by a generated hook, because a react-query client cannot express an
incremental NDJSON body. It still imports the generated event and request types, so a backend change to the
contract fails the typecheck.

## Day-to-day

```bash
make generate            # after any backend route or DTO change
git diff --stat frontend/src/shared/api/generated backend/openapi.yaml backend/env.example
```

Never edit files under `src/shared/api/generated`; change the backend and regenerate.
