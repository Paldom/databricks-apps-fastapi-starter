# AGENTS.md

Guidance for AI coding agents (and new contributors) working in `frontend/`.
Repo-wide rules live in the root `AGENTS.md`; this file covers the frontend only.

## Stack

| Concern        | Tool                                                                       |
| -------------- | -------------------------------------------------------------------------- |
| UI             | React 19, Tailwind CSS v4, shadcn/ui (`src/components/ui`)                 |
| Build          | Vite 8 (`npm run dev`, `npm run build` → `../backend/public`)              |
| Chat/assistant | @assistant-ui/react ^0.14.26 + custom NDJSON adapter (`src/lib/assistant`) |
| Server state   | TanStack Query 5 via Orval-generated hooks                                 |
| Client state   | Zustand (`src/shared/store/ui.ts`)                                         |
| API client     | Orval from `../backend/openapi.yaml` → `src/shared/api/generated`          |
| i18n           | i18next, locales in `public/locales/{en,hu}/common.json`                   |
| Mocking        | MSW (`src/mocks`), enabled in dev via `VITE_ENABLE_MOCKS`                  |
| Tests          | Vitest 4 (jsdom), 80% coverage enforced; Stryker mutation tests            |

## Hard rules

- **Never hand-edit `src/shared/api/generated/**`.** Change the backend routes/DTOs, then run `make generate`from the repo root (exports`backend/openapi.yaml`and runs`npm run api:gen`) and commit both. CI fails on stale generated code.
- **Layering:** `src/shared` must not import from `src/app`, `src/components`, `src/mocks`, or `src/test` (ESLint-enforced, including relative `../` escapes). Higher layers may import from `src/shared`.
- **`@assistant-ui/react` is at ^0.14.26.** History: the 0.12.x line had broken internal package ranges (`@assistant-ui/store` export mismatch — `tapClientLookup` crash), which is why it was previously pinned exact. After any in-range bump, verify with `npm ls @assistant-ui/react @assistant-ui/core @assistant-ui/store` and a full test run — internal export mismatches surface at runtime, not in tsc.
- **User-facing strings go through `t()`** with keys in _both_ `en` and `hu` common.json. Key types come from the en file (`src/i18next.d.ts`), so adding a key there makes it available to TypeScript.
- The chat stream endpoint (`POST /chat/stream`) is intentionally excluded from Orval generation (`tags: ['chat']` filter) — it is consumed by the hand-written streaming adapter `src/lib/assistant/chat-model-adapter.ts`.

## Chat streaming architecture

`assistant-thread.tsx` → `useChatRuntime()` (`useLocalRuntime` + adapter) → `chat-model-adapter.ts` (fetch POST `/chat/stream`, async-generator) → `ndjson-parser.ts` (chunk-safe NDJSON). Event types (`text-delta`, `tool-call-*`, `error`, `done`) are defined by the backend (`backend/openapi.yaml` schemas). In dev, `src/mocks/chat-stream-handler.ts` fakes the stream.

## Commands

```bash
npm run dev             # Vite dev server (proxies /api to the backend; MSW if VITE_ENABLE_MOCKS=true)
npm test                # Vitest
npm run test:coverage   # 80% thresholds enforced
npm run typecheck       # tsc --noEmit
npm run lint            # ESLint flat config
npm run format          # Prettier
npm run api:gen         # Regenerate API client from ../backend/openapi.yaml
npm run test:mutation   # Stryker (slow)
```

Before committing: `npm run typecheck && npm run lint && npm test` must pass; run `npm run format`.
