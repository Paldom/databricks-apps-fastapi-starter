---
name: node-packaging
description: Configures npm package artifacts - package.json exports maps, ESM-first vs dual format decisions, tsdown/tsup bundling, publint and arethetypeswrong gates, files whitelist, engines. Use when the user asks to package a library for npm, fix consumer import or type-resolution errors, or check publish-readiness. Not for version bumps, changelogs, releases, or registry auth.
license: MIT
argument-hint: [new|fix-exports|check]
---

# node-packaging

Makes a package that **installs and resolves correctly for every consumer you
claim to support** — module format, exports map, types, and tarball contents.
The failures this skill fixes: models declare "ESM-only is fine now" without
checking the consumer Node range, write exports maps whose types don't resolve,
and publish tarballs full of source and CI junk.

## When NOT to use

- Version bumps, changelogs, publishing, OIDC → `node-release`.
- Declaration *emission* / tsconfig → `node-typescript` (this skill owns how
  consumers *resolve* what was emitted).
- Dependency hygiene → `node-supply-chain`.

## Workflow

1. **Decide format from evidence, not fashion — ESM-first, not ESM-always**:
   read `package.json#engines` and the consumer reality. `require(esm)` exists
   only on specific Node lines and has real constraints (no top-level await in
   the required graph) — the support matrix and decision framework live in
   `references/packaging-playbook.md`. Dual ESM+CJS when older engines, tooling,
   or stated consumers demand it — with the dual-package hazard mitigation from
   the playbook.
2. **Write the exports map explicitly** (playbook blocks for ESM-only and dual):
   correct `types` condition placement, subpath exports only for supported API,
   `sideEffects` where true.
3. **Build**: tsdown as the current default (tsup acceptable with rationale) —
   declarations on, target matching `engines`.
4. **Tarball hygiene**: `files` whitelist (never `.npmignore` archaeology),
   `engines`, `packageManager` where the repo pins one.
5. **Gate — never skip**:
   ```bash
   bash "${CLAUDE_SKILL_DIR}/scripts/check_package.sh"
   ```
   (npm pack dry-run inspection + `publint` + `arethetypeswrong` — exact
   commands in the script; it exits non-zero on any finding.)
6. **Consumer-error diagnosis** (`ERR_REQUIRE_ESM`, "types not found"): playbook
   has the decision tree — identify the consumer's Node/module context first;
   options are documented support-range, genuine dual build, or exports fix.
   Never blind-add CJS.

## Output spec

Explicit exports map; format decision written down with the engines evidence;
build emitting exactly what exports declares; `files` whitelist; both gates
(publint, attw) clean; `npm pack --dry-run` tarball reviewed. Changing format or
exports of a published package is semver-major — say so.

## Gotchas

- The dual-package hazard (two module instances) is real — singleton/state
  packages need the playbook's mitigation or ESM-only with a documented range.
- attw failures read cryptically; the playbook maps its codes to concrete
  exports-map fixes.
- `engines` drives everything downstream (CI matrix in `node-ci`, format here) —
  set it deliberately, never inherit it silently.
- Version-gate the `require(esm)` support matrix — re-verify Node ranges against
  nodejs.org docs at use time.

## Files

- `references/packaging-playbook.md` — require(esm) matrix, format decision
  framework, exports blocks, bundler status, hazard mitigations, error decision
  tree.
- `scripts/check_package.sh` — pack dry-run + publint + attw gate; non-zero exit
  on findings; degrades with a clear message when Node/npx is unavailable.
