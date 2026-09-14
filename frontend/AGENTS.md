# AGENTS.md: frontend

Guidance for coding agents and new contributors working in `frontend/`. Repo-wide rules are in the root
`AGENTS.md`.

## Stack

| Concern      | Tool                                                                                            |
| ------------ | ----------------------------------------------------------------------------------------------- |
| UI           | React 19, Tailwind CSS v4, shadcn/ui (`src/components/ui`), Geist fonts                         |
| Build        | Vite (`npm run dev`; `npm run build` writes `../backend/public`)                                |
| Chat         | `@assistant-ui/react` 0.12 (pinned exact) + the NDJSON runtime in `src/lib/assistant`           |
| Server state | TanStack Query 5 through the Orval-generated hooks                                              |
| Client state | Zustand (`src/shared/store/ui.ts`)                                                              |
| API client   | Orval from `../backend/openapi.yaml` into `src/shared/api/generated` (see `docs/api-client.md`) |
| i18n         | i18next; `public/locales/{en,hu}/common.json`; key types from the `en` file                     |
| Mocks        | MSW (`src/mocks`), generated handlers plus the hand-written chat stream                         |
| Tests        | Vitest (jsdom) with Testing Library; coverage thresholds in `vite.config.ts`                    |

## Hard rules

- Never edit `src/shared/api/generated/**`; change the backend and run `make generate`.
- No raw `fetch` in components; the one hand-written request is the chat stream adapter.
- Every user-facing string goes through `t()` with keys in both `en` and `hu`.
- Every interactive control has an accessible name; centred text only in empty and error states.
- `@assistant-ui/react` stays pinned: the 0.12 line above 0.12.3 pulls a `@assistant-ui/core` that imports
  `tapClientLookup` from a `@assistant-ui/store` release that lacks it. Check
  `npm ls @assistant-ui/react @assistant-ui/core @assistant-ui/store` and run the tests after any bump.

## Chat runtime

`chat-shell.tsx` keys a thread by chat id → `use-chat-runtime.ts` (`useLocalRuntime` with the stored history) →
`chat-model-adapter.ts` (POST `/api/chat/stream`, NDJSON into ordered text and tool-call parts, `done` with the
trace id) → `assistant-thread.tsx` renders markdown text and one UI per tool (knowledge, Genie, fallback).

## Commands

```bash
npm run dev · npm test · npm run typecheck · npm run lint · npm run format · npm run api:gen · npm run build
```

Before committing: `npm run typecheck && npm run lint && npx vitest run`.
