---
name: node-lint
description: Sets up and tunes the linter and formatter for Node/TypeScript - Biome as the fast one-tool option or ESLint flat config plus Prettier, rule tuning, import sorting, unused-import removal, eslintrc-to-flat and ESLint-to-Biome migrations. Use when the user asks to set up or fix linting, formatting, a slow linter, ESLint, Biome or Prettier. Not for Next.js apps, type checking, or test setup.
license: MIT
argument-hint: [biome|eslint|migrate|tune]
---

# node-lint

Sets up lint + format so they catch real defects instead of fighting each other.
The failures this skill fixes: models write legacy `.eslintrc` configs that current
ESLint majors no longer load, mix two formatters, claim Biome replaces type
checking, and reset intentional rule customizations during migrations.

## When NOT to use

- Next.js apps → `nextjs-quality` owns `eslint-config-next` and RSC rules.
- Type checking / tsconfig → `node-typescript` (Biome's type-aware rules are not
  a `tsc` replacement — never claim otherwise).
- Test setup → `node-testing`; CI workflow authoring → `node-ci`.

## Workflow

1. **Detect before choosing.** Package manager (lockfile), existing configs
   (`.eslintrc*`, `eslint.config.*`, `biome.json*`, `.prettierrc*`), framework,
   and plugin needs (a11y, imports, framework-specific). Plugin needs decide the
   tool: read the decision table in `references/lint-playbook.md`.
   - **Biome** — one tool for lint+format, fastest path for TS libraries/apps
     without exotic plugin needs.
   - **ESLint (flat config only — modern majors do not load eslintrc) +
     Prettier** — when the plugin ecosystem is required.
   - Never two formatters; never ESLint stylistic rules alongside a formatter.
2. **Write the explicit config** from the playbook's starter blocks — full config,
   no reliance on version-varying defaults. Wire `package.json` scripts
   (`lint`, `format`, `lint:fix`) with `--max-warnings=0` for CI use.
3. **Migrations** (when an old setup exists): follow the playbook's path —
   official flat-config migrator or `biome migrate eslint`. Diff the effective
   rule set; preserve intentional customizations; run on the whole codebase and
   triage new findings before deleting the old config.
4. **Verify**:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/check_lint_setup.py"
   ```
   plus a clean run of the chosen tool over the repo (`npx biome check .` or
   `npx eslint . --max-warnings=0`).
5. **Report** the tool choice rationale, rules deliberately disabled, and where
   CI should call the scripts (route the workflow wiring to `node-ci`).

## Output spec

One linter + one formatter, explicit committed config, scripts wired, zero
errors/warnings on the current codebase (or a documented triage list), no
leftover legacy config files, editor settings noted.

## Gotchas

- Flat config resolves relative to each linted file's directory in current
  ESLint majors — monorepo packages can carry their own config layers.
- `biome migrate eslint` maps what it can; rules without Biome equivalents are
  dropped silently — always diff and list them.
- Version-gate everything: tool majors move fast; the playbook marks claims that
  must be re-verified against official docs at use time.
- A lint pass that only silences rules is a failure — tune by fixing signal.

## Files

- `references/lint-playbook.md` — decision table, explicit starter configs,
  migration paths, tuning discipline.
- `scripts/check_lint_setup.py` — deterministic sanity checks (single formatter,
  no legacy+flat config coexistence, scripts wired); non-zero exit on violations.
