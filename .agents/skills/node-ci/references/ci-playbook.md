# CI Playbook — GitHub Actions for Node Projects

Emit test/lint/typecheck pipelines for Node/TS repos. Pipeline structure only:
release/tagging/npm-publish/provenance → sibling skill **node-release**;
dependency-update policy, Dependabot details, lockfile integrity, pinning rationale →
sibling skill **node-supply-chain**. Workflows emitted here MUST comply with
node-supply-chain defaults (restated in "Baseline rules" below).

## Contents

1. [Baseline rules for every emitted workflow](#baseline-rules-for-every-emitted-workflow)
2. [Node version matrix — derive from `engines`, never hardcode](#node-version-matrix--derive-from-engines-never-hardcode)
3. [setup-node and caching, per package manager](#setup-node-and-caching-per-package-manager)
4. [pnpm and Yarn without Corepack](#pnpm-and-yarn-without-corepack)
5. [Complete reference workflow](#complete-reference-workflow)
6. [Fail-closed aggregator job](#fail-closed-aggregator-job)
7. [Merge queue: the `merge_group` trigger](#merge-queue-the-merge_group-trigger)
8. [Monorepo path filtering (brief)](#monorepo-path-filtering-brief)
9. [Turbo / Nx remote cache](#turbo--nx-remote-cache)

## Baseline rules for every emitted workflow

Apply all unconditionally. Never rely on implicit defaults — write the config out.

- **Least-privilege permissions, top level.** Always set explicitly:

  ```yaml
  permissions:
    contents: read
  ```

  Raise per-job only when a job provably needs more.

- **Action pinning** (supply-chain default; policy details live in node-supply-chain):
  - Official `actions/*` actions: pin by major tag (`actions/checkout@v7`,
    `actions/setup-node@v7`) and let Dependabot bump them. Note checkout v7
    refuses to check out fork PRs under `pull_request_target`/`workflow_run`
    (pwn-request hardening, 2026-06-18; opt-out is the greppable
    `allow-unsafe-pr-checkout`) — a workflow that relied on that is a
    trust-boundary bug, not a checkout regression. The guard was backported to
    6.1.0/5.1.0/4.4.0/3.7.0/2.8.0 on 2026-07-20, so floating major tags absorbed a
    breaking change automatically while SHA pins had to be bumped by hand — the
    cost of immutability, and the reason Dependabot must cover `github-actions`.
    Out of scope for the guard, and where the 2026 attacks went: `issue_comment`
    triggers running unrestricted commands in OIDC-enabled jobs
    (GHSA-9pvf-vcx3-x239), `run:` blocks fetching with `git`/`gh`, and
    `repository:` pointed at an unrelated repo.
  - Everything else (e.g. `pnpm/action-setup`): pin to the **full 40-char commit SHA**
    with a trailing version comment for reviewers. GitHub documents full-SHA pinning
    as the only immutable way to consume an action — as of mid-2026
    (verify: https://docs.github.com/en/actions/reference/security/secure-use).
    Resolve the SHA at emit time; never invent one:

    ```bash
    gh api repos/pnpm/action-setup/commits/v6 --jq .sha
    ```

  - Dependabot and SHA pins (as of mid-2026): **version updates** do cover SHA-pinned
    actions — Dependabot checks the reference ("a version number or commit
    identifier") and raises update PRs (verify:
    https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/about-dependabot-version-updates).
    Dependabot **alerts**, however, are never created for SHA-pinned actions — only
    for semver-referenced ones (same secure-use page above). Dependabot also updates
    the trailing `# vX.Y.Z` comment when it sits on the same line as the `uses:`
    (verify: https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories)
    — keep the comment on that line (it must end the line) so it stays true; a
    comment that is already wrong is *not* corrected (dependabot-core#7912).
  - Ensure a `github-actions` ecosystem entry exists in `.github/dependabot.yml`
    (config details live in node-supply-chain; verify:
    https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/keeping-your-actions-up-to-date-with-dependabot).

- **Concurrency**: cancel superseded PR runs; never cancel merge-queue runs.

  ```yaml
  concurrency:
    group: ci-${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: ${{ github.event_name == 'pull_request' }}
  ```

  (`merge_group` runs get unique `gh-readonly-queue/...` refs, so they never collide.)

- **`timeout-minutes` on every job.** The platform default is 360 minutes; a hung test
  suite must not burn six hours. Set an explicit realistic value (5–20 typical).

- **Triggers**: `push` on the default branch, `pull_request`, and `merge_group`
  (see [Merge queue](#merge-queue-the-merge_group-trigger) — required checks silently
  never run in a merge queue without it).

- **Deterministic installs**: `npm ci`, `pnpm install --frozen-lockfile`, or
  `yarn install --immutable`. Never bare `npm install` in CI.

- **Audit with the bundled checker** (`scripts/check_workflows.py`): hard-errors on
  missing or `write-all` top-level permissions, non-SHA-pinned third-party actions,
  official actions on mutable branch refs (`@main`/`@master`), EOL Node versions
  (matrix lists included), and aggregator result-checks that do not fail closed;
  `--require-merge-group` makes a missing `merge_group` an error for merge-queue
  repos. Its EOL list is version-gated — keep it in sync with the table below.

## Node version matrix — derive from `engines`, never hardcode

The matrix is a **function of `package.json#engines.node` intersected with non-EOL
release lines** — recompute it whenever either input changes; never copy a matrix
between repos.

Release-line status as of mid-2026 (verify against https://github.com/nodejs/Release —
the `schedule.json` there is the machine-readable source of truth):

| Line | Status (2026-07)                                   | EOL          |
|------|----------------------------------------------------|--------------|
| 20.x | **EOL** since 2026-04-30 — drop from all matrices  | passed       |
| 22.x | Maintenance LTS                                    | 2027-04-30   |
| 24.x | Active LTS (Maintenance from 2026-10-20)           | 2028-04-30   |
| 25.x | EOL 2026-06-01 (odd line, never LTS) — never test  | passed       |
| 26.x | Current since 2026-05-05 (LTS expected Oct 2026)   | —            |

Derivation rule:

1. Read `engines.node` (e.g. `">=22.12"` or `"^22.12 || >=24"`).
2. Take every **even** major that satisfies the range and is not EOL → required matrix
   entries (here: 22, 24).
3. Add the Current line (26) if it satisfies the range — recommended for early signal;
   allow it to be marked non-blocking only if the team accepts that.
4. If `engines` still permits an EOL line, that is an `engines` bug — fix `engines`
   first, do not paper over it in the matrix.

Preferred form — explicit matrix with a provenance comment (reviewable, deterministic):

```yaml
strategy:
  fail-fast: false          # always explicit; report every failing line
  matrix:
    # Derived 2026-07 from engines.node ">=22.12" ∩ non-EOL lines
    # (https://github.com/nodejs/Release). Re-derive when engines changes
    # or a line reaches EOL.
    node: ['22', '24', '26']
```

Optional dynamic derivation (only when the repo insists on zero-touch): a first job
fetches that `schedule.json`, keeps lines where `start <= today <= end`, intersects
with `engines.node` (`semver` package), emits `matrix=[...]` to `$GITHUB_OUTPUT`;
downstream: `node: ${{ fromJSON(needs.derive.outputs.matrix) }}`. Semver subtlety:
test the line's *latest* release, not `X.0.0` (`^22.12` rejects `22.0.0`). Verify
script behavior at use time.

For single-version jobs (lint, typecheck), do not hardcode either — use
`node-version-file: package.json`. setup-node reads, in order, `volta.node`,
`devEngines.runtime` (name `node`), then `engines.node`, and resolves semver ranges —
as of setup-node v7, September 2026
(verify: https://github.com/actions/setup-node/blob/main/docs/advanced-usage.md).

## setup-node and caching, per package manager

Current major is **`actions/setup-node@v7`** (v7.0.0, July 2026)
(verify: https://github.com/actions/setup-node). v5 introduced automatic caching when
`packageManager` is set; v6 restricted auto-caching to npm only. **Do not rely on
either behavior** — always set `cache:` and `cache-dependency-path:` explicitly, keyed
to the lockfile:

| Package manager | `cache:` | `cache-dependency-path:` | Install command                  |
|-----------------|----------|--------------------------|----------------------------------|
| npm             | `npm`    | `package-lock.json`      | `npm ci`                         |
| pnpm            | `pnpm`   | `pnpm-lock.yaml`         | `pnpm install --frozen-lockfile` |
| yarn (berry)    | `yarn`   | `yarn.lock`              | `yarn install --immutable`       |

The `cache:` input requires the package manager binary to already exist on the runner
(setup-node shells out to it to locate the store). npm ships with Node; Yarn is
preinstalled on GitHub-hosted runners (standalone, **not** via Corepack — next
section); **pnpm is not present** — install it first (next section).

## pnpm and Yarn without Corepack

Do **not** use `corepack enable` in emitted workflows. The Node TSC voted to stop
distributing Corepack: Node 25+ official distributions omit it entirely; it remains
only an experimental leftover in 22/24 — as of mid-2026 (verify:
https://github.com/nodejs/corepack and https://github.com/nodejs/nodejs.org/issues/7555).
A pipeline assuming Corepack breaks the moment the matrix includes Node 26.

Instead, use `pnpm/action-setup` (current major v6 as of mid-2026, verify:
https://github.com/pnpm/action-setup), which reads the pnpm version from the
`packageManager` field in `package.json` — keep that field as the single source of
truth and **omit** the action's `version:` input. Ordering is mandatory:
`pnpm/action-setup` must run **before** `actions/setup-node` with `cache: pnpm`,
because setup-node invokes `pnpm store path` during cache setup.

```yaml
steps:
  - uses: actions/checkout@v7
  - uses: pnpm/action-setup@<full-40-char-sha> # vX.Y.Z  (resolve SHA at emit time)
    # no `version:` input — pnpm version comes from package.json "packageManager"
  - uses: actions/setup-node@v7
    with:
      node-version-file: package.json
      cache: pnpm
      cache-dependency-path: pnpm-lock.yaml
  - run: pnpm install --frozen-lockfile
```

**Yarn without Corepack**: GitHub-hosted Ubuntu images preinstall classic Yarn 1.22.x
as a standalone tool (verify: https://github.com/actions/runner-images, Ubuntu
readme; on self-hosted runners, `npm install -g yarn` before setup-node). For modern
Yarn (Berry), commit the release into the repo: `yarn set version <ver> --yarn-path`
stores it under `.yarn/releases/` and sets `yarnPath` in `.yarnrc.yml`, and any Yarn
binary — the preinstalled 1.22.x included — then executes that file instead of itself
(verify: https://yarnpkg.com/configuration/yarnrc#yarnPath and
https://yarnpkg.com/cli/set/version). A bare `packageManager` field is not enough to
select the Yarn version in CI: resolving it is Corepack's job.

## Complete reference workflow

npm variant; swap the setup block per the tables above for pnpm/yarn.

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
  merge_group:
    types: [checks_requested]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with:
          node-version-file: package.json   # engines.node, not a hardcoded number
          cache: npm
          cache-dependency-path: package-lock.json
      - run: npm ci
      - run: npm run lint

  typecheck:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with:
          node-version-file: package.json
          cache: npm
          cache-dependency-path: package-lock.json
      - run: npm ci
      - run: npm run typecheck

  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        # Derived 2026-07 from engines.node ∩ non-EOL lines — see matrix section.
        node: ['22', '24', '26']
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with:
          node-version: ${{ matrix.node }}
          cache: npm
          cache-dependency-path: package-lock.json
      - run: npm ci
      - run: npm test

  ci-ok:
    name: CI OK
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions: {}
    needs: [lint, typecheck, test]
    if: always()
    steps:
      - name: Fail if any needed job was not a success
        if: >-
          needs.lint.result != 'success' ||
          needs.typecheck.result != 'success' ||
          needs.test.result != 'success'
        run: |
          echo "A required job failed, was cancelled, or was skipped:"
          echo '${{ toJSON(needs) }}'
          exit 1
```

## Fail-closed aggregator job

Branch protection / merge-queue required checks must reference **exactly one** check:
`CI OK`. Never list matrix legs as required checks — renaming a leg or changing the
matrix silently orphans the requirement.

Why each piece of the `ci-ok` job above is load-bearing:

- `if: always()` — without it, one failed dependency marks the aggregator *skipped*,
  and depending on ruleset semantics a skipped check can stall as "Expected" or, worse,
  be treated as passing by other automation. Fail closed: always run, then decide.
- The step tests every needed job's `result != 'success'` — the one predicate that
  fails closed over `failure`, `cancelled`, **and** `skipped` (the four possible
  values of `needs.<job>.result` — verify:
  https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#needs-context).
  Checking only `failure` is the classic hole: a cancelled or transitively-skipped
  job yields a green aggregator; the checker script errors on such weaker forms.
- `permissions: {}` — the aggregator executes no checkout and needs nothing.
- Every job that must gate merges appears in `needs` **and** in the `if:` test — a
  job absent from either is invisible to the gate; keep the two lists in lockstep.

If a needed job may *legitimately* skip (path-gated docs job, etc.), do not weaken the
blanket check — replace it with per-job assertions and allow `skipped` only for that
specific job, gated on the change-detection output that caused the skip.

## Merge queue: the `merge_group` trigger

If the repo uses (or may adopt) GitHub merge queues, every workflow providing required
checks MUST also trigger on `merge_group`; otherwise the checks never run for queued
merge groups, the required status is never reported, and the merge fails — as of
mid-2026 (verify:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#merge_group).
Specify the only current activity type explicitly to stay future-proof:

```yaml
on:
  merge_group: { types: [checks_requested] }
```

Emit this trigger by default: it is inert without a merge queue and prevents a
guaranteed foot-gun later; keep `cancel-in-progress` scoped to `pull_request` only.
The checker's `--require-merge-group` flag enforces its presence on merge-queue repos.

## Monorepo path filtering (brief)

Avoid `on.pull_request.paths` for workflows that provide required checks: a
path-filtered workflow that does not run leaves its required check unreported, which
stalls PRs and breaks merge queues. Instead, always run the workflow and filter
*inside* it: a first `changes` job computes affected areas (`git diff --name-only`
against the merge base, or a SHA-pinned filter action), exposes them as outputs used
in step-level `if:` conditions downstream — gated jobs still report `success`
(cheaply) instead of `skipped`, keeping the strict aggregator intact. For per-package
pipelines, prefer the task runner's graph (`turbo run --filter=...[HEAD^]`,
`nx affected`) over hand-maintained path lists.

## Turbo / Nx remote cache

For monorepos on Turborepo or Nx, wire the remote cache so CI reuses task results:
Turbo — `TURBO_TOKEN` / `TURBO_TEAM` from repo secrets, run via `turbo run lint
typecheck test`; Nx — `NX_CLOUD_ACCESS_TOKEN`, `nx affected -t lint,typecheck,test`.
Use a **read-only** CI token where supported; GitHub does not expose secrets to fork
PRs, so the cache degrades to cold builds there — correct behavior, never relax
secret access to "fix" it. Enable cache-artifact signing/verification where offered.
Token mechanics drift — verify at use time: https://turborepo.com/docs,
https://nx.dev/docs.
