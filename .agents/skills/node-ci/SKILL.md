---
name: node-ci
description: Authors GitHub Actions CI for Node projects - version matrices derived from engines, setup-node caching, pnpm setup without corepack, a fail-closed all-checks aggregator, merge_group support, concurrency. Use when the user asks to set up CI, add a Node test matrix, cache installs, or fix required checks and merge queues. Not for release/publish pipelines or dependency-update policy.
license: MIT
argument-hint: [new|matrix|speed|merge-queue]
---

# node-ci

Authors CI that is **derived from the repo, fails closed, and is supply-chain
clean by construction**. The failures this skill fixes: models hardcode Node
versions that drift from `engines` (or are EOL), write aggregator checks that
pass when jobs are skipped, use `corepack enable` on runners where corepack no
longer ships, and emit workflows with unpinned actions and default-broad
permissions.

## When NOT to use

- Release/publish workflows → `node-release`.
- What the checks run (lint rules, test config) → `node-lint` /
  `node-testing` / `node-typescript`; this skill wires them.
- Dependabot/dependency policy → `node-supply-chain` (but every workflow this
  skill emits complies with its pinning/permissions rules).

## Workflow

1. **Derive, don't hardcode**: matrix from `package.json#engines` intersected
   with maintained Node lines (verify current LTS/EOL against the nodejs.org
   release schedule — table version-gated in `references/ci-playbook.md`).
   Optional next-Current line as allowed-failure.
2. **Package manager from the lockfile**: setup-node cache keyed to the right
   lockfile; pnpm via its setup action — do **not** rely on corepack on current
   runners (not bundled with newer Node lines; verified in the playbook).
3. **Structure**: lint / typecheck / test jobs → one **fail-closed aggregator**
   as the only required check: `if: always()` with an explicit result test that
   fails on `failure`, `cancelled`, **and** `skipped` (exact YAML in the
   playbook — a naive `needs` chain passes on skips).
4. **Merge queues**: every workflow backing a required check declares
   `merge_group` alongside `pull_request`, or the queue silently stalls.
5. **Hygiene by construction**: top-level `permissions: contents: read`,
   per-job elevation only; third-party actions SHA-pinned with version comment
   (official `actions/*` by major tag + Dependabot); `concurrency` with
   cancel-in-progress; `timeout-minutes` everywhere.
6. **Speed work is measured work**: read run timings first; then lockfile-keyed
   caching, matrix pruning, suite splitting — never delete gates for speed
   silently.
7. **Verify**:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/check_workflows.py"
   ```
   then push and confirm the aggregator turns red on a deliberately failed leg
   (prove fail-closed once).

## Output spec

Workflows that pass schema validation and the checker script; matrix documented
against `engines`; a single aggregator required check proven to fail on
failed/cancelled/skipped legs; merge_group present when queues are on; no
unpinned third-party actions; no default-broad permissions.

## Gotchas

- Required-check names match the *reported* check (job `name:`), not filenames —
  renames silently orphan branch rules.
- A matrix leg that's skipped by path filters still satisfies naive aggregators —
  the playbook's result-check is the fix.
- `cancel-in-progress: true` on `main` pushes can cancel deploy-adjacent runs —
  scope concurrency groups to refs deliberately.
- Version-gate the LTS table and setup-action majors; re-verify at authoring
  time.

## Files

- `references/ci-playbook.md` — engines-derived matrices, cache/pnpm setup,
  fail-closed aggregator YAML, merge_group, monorepo filtering, remote cache.
- `scripts/check_workflows.py` — static workflow audit (unpinned third-party
  actions, missing permissions, EOL node versions, aggregator/merge_group
  presence); non-zero exit on violations.
