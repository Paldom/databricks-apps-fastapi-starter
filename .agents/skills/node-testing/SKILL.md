---
name: node-testing
description: Builds unit and integration test infrastructure for Node/TS/React - Vitest or node:test with explicit config, Jest-to-Vitest migration, v8 coverage gates that fail CI, React Testing Library, mocking discipline, flaky-test triage. Use when the user asks to set up tests, add coverage thresholds, pick a test runner, or fix a flaky setup. Not for E2E browser suites, lint rules, or CI workflows.
license: MIT
argument-hint: [library|react-app|coverage|flaky]
---

# node-testing

Builds test infrastructure where green means something: explicit runner config,
coverage that **fails** the build instead of decorating it, and mocks that don't
lie. The failures this skill fixes: models default to legacy Jest setups, write
coverage reports nobody gates on, and stretch component tests into flaky
pseudo-E2E.

## When NOT to use

- E2E / real-browser flows → out of this repo's scope; route to Playwright and
  its docs (explicit non-goal).
- Lint → `node-lint`; tsconfig → `node-typescript`.
- Wiring jobs/matrices in GitHub Actions → `node-ci` (this skill defines *what*
  to run; that one defines *where*).

## Workflow

1. **Pick the runner by the decision table** in
   `references/testing-playbook.md`:
   - **Vitest** for anything non-trivial: TS/JSX native, watch UX, snapshots,
     mocking surface, React work.
   - **node:test** for dependency-free pure-Node libraries where zero
     dependencies is itself the feature — with its trade-offs stated (loader for
     TS, weaker watch/snapshot ergonomics).
   - Modernizing from Jest → Vitest is the default path (API-compatible for
     most suites); playbook has the migration steps.
2. **Write explicit config** (no version-default reliance): environment
   (`node` / `jsdom` / browser mode with tradeoff), globals policy, setup files.
3. **Coverage as a gate**: v8 provider with explicit `thresholds` that fail the
   run. Philosophy: coverage finds gaps, it doesn't prove quality — prefer
   PR-delta discipline over chasing a global vanity number; never raise
   thresholds to force shallow tests.
4. **React**: React Testing Library + user-event on Vitest; test behavior via
   roles/text, not implementation details; real components from the repo in
   examples, never toys.
5. **Mocking discipline**: mock at boundaries (network, clock, fs), not internal
   modules; fake timers come with the pitfalls list in the playbook.
6. **Verify**: full suite green locally, coverage gate demonstrably fails when a
   threshold is unmet (prove it once), scripts wired (`test`, `test:coverage`).

## Output spec

Runner chosen with written rationale; explicit committed config; coverage
thresholds that fail CI; at least one real test demonstrating the setup
(rendering a real component / exercising a real module); scripts wired; flaky
triage checklist applied when that was the complaint.

## Gotchas

- v8 coverage with AST remapping matches istanbul-level accuracy on modern
  Vitest — version-gate this and re-verify on major bumps.
- jsdom is not a browser: anything relying on real layout, navigation, or
  workers belongs in Playwright, not a heavier unit-test mock.
- `vi.mock` hoists — factory functions referencing outer variables break
  silently; playbook shows the safe patterns.
- A passing suite after `--changed` filtering is not a green suite — full runs
  gate merges (where: `node-ci`).

## Files

- `references/testing-playbook.md` — runner decision table, explicit configs,
  coverage gating, RTL patterns, mocking pitfalls, flaky triage.
