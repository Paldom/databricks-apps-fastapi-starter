# Testing Playbook — Unit & Integration Tests for Node/TS/React

Scope: unit and integration testing for Node.js libraries, TypeScript services, and
React components. **Not in scope:** end-to-end/browser suites (write those with
Playwright — https://playwright.dev/docs/intro) and CI workflow authoring (route to
the `node-ci` skill; this file only defines the commands CI should run).

## Contents

- [Runner decision: Vitest vs node:test](#runner-decision-vitest-vs-nodetest)
- [Vitest config — library (Node environment)](#vitest-config--library-node-environment)
- [Vitest config — React app (jsdom vs browser mode)](#vitest-config--react-app-jsdom-vs-browser-mode)
- [Coverage: v8 provider with enforced thresholds](#coverage-v8-provider-with-enforced-thresholds)
- [React Testing Library + user-event setup](#react-testing-library--user-event-setup)
- [Mocking discipline](#mocking-discipline)
- [Coverage philosophy](#coverage-philosophy)
- [Flaky-test triage checklist](#flaky-test-triage-checklist)

## Runner decision: Vitest vs node:test

Pick one runner per package. Do not mix runners in a single package.

| Criterion | Vitest 5 (current major since 2026-09-03; many repos still on 4.x — verify: https://vitest.dev/blog/vitest-5) | `node:test` (built-in) |
|---|---|---|
| Dependencies added | vitest + plugins | Zero — ships with Node |
| TypeScript | Any TS, transformed by Vite/esbuild | Erasable syntax only via type stripping — stable since Node v24.12.0 (verify: https://nodejs.org/api/typescript.html). No `enum`, no namespaces with runtime code, no legacy decorators emit |
| Coverage | v8/istanbul providers, enforced thresholds, stable | Still **experimental** (`--experimental-test-coverage`) as of Node 26 (verify: https://nodejs.org/api/test.html) |
| Watch mode | Stable, default dev loop | **Experimental** as of Node 26 (verify: https://nodejs.org/api/test.html) |
| Module mocking | `vi.mock`, stable | Behind `--experimental-test-module-mocks` flag (verify: https://nodejs.org/api/cli.html) |
| DOM testing | jsdom env or stable browser mode | None built in; wiring jsdom manually is on you |
| Snapshots | Built in | Stable since Node v23.4.0 |
| Ecosystem (RTL, MSW, matchers) | First-class | Works, but you assemble everything |

Decision rules:

- **Pure-Node library with zero runtime deps** (CLI tool, small utility package):
  prefer `node:test`. Keeping the dependency tree empty is worth losing the polish;
  supply-chain surface stays minimal (deep dive: `node-supply-chain` skill).
- **Anything with React, DOM, path aliases, non-erasable TS, or a coverage gate**:
  use Vitest. The experimental status of node:test coverage means its output format
  and flags may change under you.
- **Monorepo**: standardize on Vitest across packages; use `test.projects` for
  per-package config.

Minimal `node:test` invocation (Node ≥ 24; type stripping needs no flag):

```jsonc
// package.json
{
  "scripts": {
    "test": "node --test \"src/**/*.test.ts\"",
    "test:coverage": "node --test --experimental-test-coverage --test-coverage-lines=80 --test-coverage-branches=70 --test-coverage-functions=80 \"src/**/*.test.ts\""
  }
}
```

Threshold flags (`--test-coverage-lines` etc.) fail the run when unmet, but inherit
coverage's experimental status — re-verify flags at use time against
https://nodejs.org/api/cli.html.

## Vitest config — library (Node environment)

Never rely on Vitest defaults (pool, environment, include globs, coverage include
have all changed across majors). State everything explicitly:

```ts
// vitest.config.ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    globals: false,               // import { describe, it, expect } from 'vitest'
    pool: 'forks',                // process isolation; 'threads' is faster but leaks less-isolated state
    isolate: true,
    testTimeout: 5_000,
    hookTimeout: 10_000,
    restoreMocks: true,           // undo vi.spyOn between tests
    unstubGlobals: true,          // undo vi.stubGlobal between tests
    unstubEnvs: true,             // undo vi.stubEnv between tests
    // Do NOT enable sequence.shuffle here: unpinned shuffling makes CI runs
    // nondeterministic. Use it as a triage tool with a fixed seed — see the
    // flaky-test triage checklist below.
  },
})
```

Prefer `globals: false` in libraries: explicit imports keep files portable and make
the ESLint/TS story trivial. Turn `globals: true` on only when a dependency (e.g.
some testing-library cleanup integrations) requires it.

**Vitest 5 migration notes** (as of 2026-09; verify:
https://vitest.dev/guide/migration/): requires Node >= 22.12 and Vite >= 6.4;
`clearMocks` now defaults to `true`; `vi.mock`/`vi.hoisted` inside a function,
block or `describe`/`test` callback throws (it only warned before); async
assertions (`resolves`, `rejects`, `toMatchFileSnapshot`) fail the test when not
awaited; `test.sequential` is removed (use `concurrent: false`); browser
locators match text exactly by default; artifacts consolidate under `.vitest/`.
Keep 4.x blocks for repos not yet upgraded — the config shapes below are the same.

## Vitest config — React app (jsdom vs browser mode)

Two options, both stable as of Vitest 4 and 5:

- **jsdom environment** — fast, runs in Node, no browser processes. But it is a
  simulation: no real layout (`getBoundingClientRect` returns zeros), no real
  navigation, CSS is mostly inert. Good default for component logic tests.
- **Browser mode** — stable since Vitest 4.0 (verify:
  https://vitest.dev/guide/browser/); runs tests in a real browser via a provider
  package (`@vitest/browser-playwright`, `@vitest/browser-webdriverio`, or
  `@vitest/browser-preview`). Real rendering and events; slower startup, heavier CI.
  Choose it when components depend on layout, scrolling, viewport, or real events.
  This is still component-level testing — full-app flows remain Playwright E2E
  territory (out of scope here).

jsdom config (the common case):

```ts
// vitest.config.ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    globals: true,                       // required by some jest-dom/cleanup setups; decide once
    setupFiles: ['./src/test/setup.ts'],
    pool: 'forks',
    isolate: true,
    restoreMocks: true,
    unstubGlobals: true,
    css: false,                          // don't process CSS in unit tests
  },
})
```

Browser-mode variant of the `test` block (Vitest 4/5 shape — provider is a package,
context imports come from `vitest/browser`):

```ts
import { playwright } from '@vitest/browser-playwright'

// inside defineConfig({ test: { ... } })
browser: {
  enabled: true,
  provider: playwright(),
  instances: [{ browser: 'chromium' }],
  headless: true,
},
```

Do not keep both jsdom and browser mode for the same tests; pick per test project.

## Coverage: v8 provider with enforced thresholds

Use the `v8` provider. AST-based remapping of v8 coverage (`ast-v8-to-istanbul`)
produces Istanbul-accurate reports at v8 speed. It shipped opt-in in Vitest 3.2.0
as `coverage.experimentalAstAwareRemapping`; Vitest 4.0 removed that option and made
AST remapping the default and only remapping method. Vitest 5 keeps the `v8`
provider; its Istanbul reporting stack moved to the maintained `@vitest/istanbuljs`
fork, and `coverage.thresholds.perFile` now applies per glob pattern rather than to
every threshold set (as of 2026-09; verify: https://vitest.dev/guide/coverage and
https://vitest.dev/guide/migration/).

Thresholds must **fail the run**, not just print a report. Vitest exits non-zero
with `Coverage for lines (X%) does not meet global threshold (Y%)` when unmet
(verify: https://vitest.dev/config/coverage). Explicit block:

```ts
// inside defineConfig({ test: { ... } })
coverage: {
  provider: 'v8',
  enabled: false,                  // opt in via `vitest run --coverage`
  include: ['src/**/*.{ts,tsx}'],  // set explicitly: default only counts files imported by tests,
                                   // so never-imported modules would be invisible
  exclude: ['src/**/*.test.*', 'src/**/*.d.ts', 'src/test/**'],
  reporter: ['text', 'html', 'lcov', 'json-summary'],
  reportOnFailure: true,           // still emit report when tests fail (useful for PR tooling)
  thresholds: {
    lines: 80,
    functions: 80,
    branches: 70,
    statements: 80,
    // Negative numbers mean "max N uncovered units", e.g. lines: -10
    // Per-path override:
    'src/core/**': { lines: 90, branches: 85 },
  },
},
```

Notes:
- `thresholds.perFile: true` enforces per file instead of aggregate — stricter, use
  for small critical packages, not sprawling apps.
- `thresholds.autoUpdate: true` ratchets thresholds up automatically; only enable
  once coverage is healthy, otherwise it locks in noise.
- Keep `json-summary` in reporters — PR-delta tooling consumes it.

## React Testing Library + user-event setup

Versions (as of mid-2026, verify: https://github.com/testing-library/react-testing-library/releases):
`@testing-library/react` 16.x supports React 19 (since 16.1.0). Since 16.0.0,
`@testing-library/dom` is a **peer dependency you must install explicitly**. Use
`@testing-library/user-event` 14.x and `@testing-library/jest-dom` for matchers.

```bash
npm i -D @testing-library/react @testing-library/dom @testing-library/user-event @testing-library/jest-dom jsdom
```

```ts
// src/test/setup.ts  (referenced from setupFiles)
import '@testing-library/jest-dom/vitest'
```

Test pattern — always `userEvent.setup()`, never the deprecated direct calls:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

it('submits the form', async () => {
  const user = userEvent.setup()
  render(<SignupForm />)
  await user.type(screen.getByLabelText(/email/i), 'a@b.co')
  await user.click(screen.getByRole('button', { name: /sign up/i }))
  expect(await screen.findByText(/welcome/i)).toBeInTheDocument()
})
```

Rules:
- Query by role/label/text (what users perceive); reach for `data-testid` last.
- Prefer `findBy*` (built-in waiting) over `getBy*` wrapped in `waitFor`.
- Never assert on component internals or state; assert rendered output.
- All `user.*` calls return Promises — always `await` them.

## Mocking discipline

Default stance: mock at the process boundary (network, clock, filesystem), not
between your own modules. Every internal `vi.mock` couples the test to the import
graph and rots on refactor.

**`vi.mock` pitfalls:**
- `vi.mock('./mod')` calls are hoisted above imports. Any variable used inside the
  factory must be created with `vi.hoisted(() => ...)`.
- Prefer `vi.mock('./mod', { spy: true })` (auto-spies, real implementations kept)
  or dependency injection over full module-replacement factories.
- With `restoreMocks: true` set in config (see above), do not hand-write
  `afterEach(() => vi.restoreAllMocks())`.

**fetch/HTTP mocking:** use MSW (2.x as of mid-2026, verify: https://mswjs.io/docs/)
so tests intercept at the network layer and don't care whether code calls `fetch`,
axios, or a client SDK:

```ts
// src/test/setup.ts
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { afterAll, afterEach, beforeAll } from 'vitest'

export const server = setupServer(
  http.get('/api/user', () => HttpResponse.json({ name: 'Ada' })),
)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

`onUnhandledRequest: 'error'` is non-negotiable: silent passthrough hides missing
handlers. For a one-off unit test, `vi.stubGlobal('fetch', vi.fn(...))` is
acceptable; `unstubGlobals: true` cleans it up.

**Fake timers pitfalls:**
- Always pair: `beforeEach(() => vi.useFakeTimers())` /
  `afterEach(() => vi.useRealTimers())`. A leaked fake clock breaks unrelated tests.
- Fake timers freeze `Date` too by default — timestamp-diff logic will read 0ms
  elapsed unless you advance the clock.
- user-event + fake timers deadlocks unless you wire them together:
  `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`.
- Code awaiting promises between timer ticks needs `await vi.advanceTimersByTimeAsync(ms)`
  or `await vi.runAllTimersAsync()` — the sync variants skip microtasks.
- `vi.runAllTimers()` on `setInterval`-style code loops forever; advance by explicit
  durations instead.

## Coverage philosophy

- Coverage is a **gap-finder, not a quality proof**. 100% covered code can still be
  wrong; assertions prove behavior, coverage only proves execution.
- Enforce **PR-delta coverage** (changed lines in this PR are tested) over ratcheting
  a global number. Global vanity thresholds incentivize assertion-free "coverage
  tests"; delta gates keep pressure where the risk is (wiring the gate into CI
  belongs to the `node-ci` skill).
- Keep the global threshold a modest floor (e.g. 70–80) to catch regressions; raise
  per-directory thresholds only on genuinely critical code.
- Read the HTML report for uncovered *branches* (error paths, empty-input paths) —
  those are where real bugs live, and line % hides them.
- Never write a test whose only assertion is "it did not throw" just to lift a number.

## Flaky-test triage checklist

Work top to bottom; quarantine (skip + tracking issue) only after step 8.

1. **Reproduce**: `vitest run path/to.test.ts --retry=0` in a loop (e.g.
   `for i in {1..50}; do ... || break; done`). No repro locally → suspect env/CI parallelism.
2. **Order dependence**: shuffle with a pinned seed —
   `vitest run --sequence.shuffle --sequence.seed=12345` — so a failing order can
   be replayed exactly. The seed defaults to `Date.now()`, i.e. a different order
   every run (verify: https://vitest.dev/config/sequence), so never turn shuffle on
   in the default config; if you shuffle in CI to hunt order coupling, always pass
   an explicit seed and echo it in the job output. A test passing alone but failing
   in suite means leaked state (module-level caches, globals, env vars, DB rows).
3. **Isolation config**: confirm `pool: 'forks'`, `isolate: true` while debugging;
   if the flake disappears, a shared-state leak is confirmed — find it, don't just
   keep isolation as a band-aid for a real bug.
4. **Unawaited async**: look for missing `await` on `user.*`, `findBy*`, promises in
   the code under test; enable `@typescript-eslint/no-floating-promises` in test
   files (rule setup: `node-lint` skill).
5. **Real time/clock**: any `setTimeout`, debounce, `Date.now()`, or "wait 100ms and
   assert" is a flake factory — replace sleeps with fake timers or `findBy*`/`vi.waitFor`.
6. **Leaked timers/handles**: use Vitest's hanging-process reporter to find open
   handles keeping the run alive (verify current flag/reporter name at use time:
   https://vitest.dev/guide/).
7. **Network**: confirm MSW `onUnhandledRequest: 'error'`; a flake that hits real
   network is an integration test misfiled as a unit test.
8. **Resource contention**: CI-only flakes under parallelism → shared ports, temp
   dirs, or DB schemas. Randomize per-worker resources (port 0, `mkdtemp`, schema
   per worker) rather than reducing concurrency.
9. **Never** fix a flake by adding retries or widening timeouts without a diagnosed
   cause; retries convert a visible bug into an invisible one.
