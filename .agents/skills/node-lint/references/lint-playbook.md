# Lint & Format Playbook — Node/TypeScript

Scope: choosing, configuring, migrating, and enforcing lint/format tooling for Node/TS
projects and libraries.
Routing: Next.js apps (`eslint-config-next`, framework-specific rules) → sibling skill
`nextjs-quality`. Type *checking* (`tsc --noEmit`, tsconfig strictness) is out of scope —
typed **lint rules** are in scope here.

## Contents

- [1. Choose a stack](#1-choose-a-stack)
- [2. Version facts as of mid-2026](#2-version-facts-as-of-mid-2026)
- [3. Starter config A — Biome on a TypeScript library](#3-starter-config-a--biome-on-a-typescript-library)
- [4. Starter config B — ESLint flat + typescript-eslint + Prettier](#4-starter-config-b--eslint-flat--typescript-eslint--prettier)
- [5. Migration paths](#5-migration-paths)
- [6. Editor and CI wiring](#6-editor-and-ci-wiring)
- [7. Rule tuning: fix signal, not silence](#7-rule-tuning-fix-signal-not-silence)

## 1. Choose a stack

Pick ONE primary stack per repo. Do not run two formatters on the same files.

| Stack | Pick when | Trade-offs |
|---|---|---|
| **Biome** (lint + format + import sorting, one binary) | New projects; teams that want one tool, one config, fast CI; TS/JS/JSON/CSS codebases | Type-aware rules run on Biome's own inference (no tsc process) — fast but narrower coverage than typescript-eslint; smaller plugin ecosystem (GritQL-pattern plugins, not ESLint plugins) |
| **ESLint v10 + typescript-eslint + Prettier** | Existing ESLint investment; need niche ESLint plugins; want maximum typed-rule coverage | Slowest of the three; three tools/configs to keep aligned; typed linting spawns TypeScript work |
| **Oxlint** (+ Prettier for formatting) | Very large codebases where lint speed dominates; want ESLint-compatible rules at Rust speed | Linter only (formatting is a separate tool); JS-plugin support is alpha; custom-parser frameworks (Vue/Svelte/Angular) not fully supported |

Hybrid pattern: run Oxlint first for speed, then ESLint for the rules Oxlint lacks, with
`eslint-plugin-oxlint` disabling the overlap. Use only when neither tool alone suffices —
two configs cost real maintenance.

Decision shortcuts:

- Greenfield TS library or service → Biome (Section 3).
- Repo already on ESLint and it works → stay; upgrade to flat config/v10 (Section 5).
- Next.js app → route to `nextjs-quality`; do not hand-roll ESLint there.

## 2. Version facts as of mid-2026

Version-gated claims — re-verify at use time via the linked primary docs.

- **ESLint v10** (Feb 2026; v9 reached EOL on 2026-08-06, so v10 is the only supported
  line) removed the eslintrc system entirely: `.eslintrc.*` and
  `.eslintignore` are ignored, `ESLINT_USE_FLAT_CONFIG` is gone, and flat
  `eslint.config.js` is the only format. Config lookup now starts from each linted
  file's directory, not the cwd. Requires Node.js ^20.19.0 || ^22.13.0 || >=24.
  ESLint v9.x EOL is 2026-08-06.
  (verify: https://eslint.org/docs/latest/use/migrate-to-10.0.0)
- **typescript-eslint v8.x** supports ESLint ^8.57.0 || ^9.0.0 || ^10.0.0; typed linting
  uses `projectService: true`. It declares `typescript >=4.8.4 <6.1.0` — **no
  TypeScript 7 support** (forcing it crashes typescript-estree with `Cannot read
  properties of undefined (reading 'Cjs')`; the tracking issue was closed
  not-planned). On TS 7 the choices are: pin the lint-time TypeScript to 6.x via the
  `@typescript/typescript6` alias, switch type-aware linting to Oxlint + tsgolint
  (stable since 2026-07-22, needs TS 7), or accept Biome's partial type-awareness.
  ESLint 9 → 10 migration: `npx codemod @eslint/v9-to-v10`.
  (verify: https://typescript-eslint.io/users/dependency-versions/)
- **Prettier 3.9.x** is current.
  (verify: https://github.com/prettier/prettier/releases)
- **eslint-config-prettier v10.x**: import from `eslint-config-prettier/flat`, place last.
  (verify: https://github.com/prettier/eslint-config-prettier)
- **Biome 2.5.x** ("Biome v2 — Biotype" line): type-aware lint rules without a tsc
  process, via its own inference; enabled through linter *domains* (`types`, `project`),
  which trigger whole-project scanning (slower, still no tsc). Monorepo-nested
  `biome.json`, GritQL plugins, bulk suppressions.
  (verify: https://biomejs.dev/linter/domains/ and https://biomejs.dev/blog/)
- **Oxlint** (1.8x) ships 865+ built-in rules (ESLint core, typescript, react, jest,
  vitest, import, unicorn, jsx-a11y ports). JS-plugin support (ESLint v9+ plugin API
  compat) reached **alpha** in March 2026. Type-aware mode via `--type-aware` +
  `oxlint-tsgolint` requires TypeScript 7.0+; rule coverage is close to complete
  but not total (as of 2026-09).
  (verify: https://oxc.rs/docs/guide/usage/linter and
  https://oxc.rs/docs/guide/usage/linter/js-plugins)

## 3. Starter config A — Biome on a TypeScript library

Install pinned: `npm i -D -E @biomejs/biome`. Write every setting explicitly — do not
rely on defaults, which shift between minors.

```jsonc
// biome.json — match $schema to the installed version
{
  "$schema": "https://biomejs.dev/schemas/2.5.12/schema.json",
  "vcs": { "enabled": true, "clientKind": "git", "useIgnoreFile": true },
  "files": {
    "includes": ["**", "!**/dist/**", "!**/coverage/**", "!**/node_modules/**"]
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100,
    "lineEnding": "lf"
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "double",
      "semicolons": "always",
      "trailingCommas": "all"
    }
  },
  "linter": {
    "enabled": true,
    "rules": { "recommended": true },
    "domains": {
      "project": "recommended",
      "types": "recommended",
      "test": "recommended"
    }
  },
  "assist": {
    "enabled": true,
    "actions": { "source": { "organizeImports": "on" } }
  }
}
```

Notes:

- `domains.types` / `domains.project` enable type-aware and cross-module rules; they make
  Biome scan the whole project. Drop them if lint latency matters more than the rules.
- `files.includes` uses `!` negation; with `vcs.useIgnoreFile: true`, `.gitignore`
  entries are also excluded.

```jsonc
// package.json (scripts)
{
  "scripts": {
    "lint": "biome lint .",
    "format": "biome format --write .",
    "format:check": "biome format .",
    "check": "biome check --write .",
    "check:ci": "biome ci --error-on-warnings ."
  }
}
```

`biome check` = lint + format + assist in one pass; `biome ci` is its read-only CI twin.

## 4. Starter config B — ESLint flat + typescript-eslint + Prettier

Install: `npm i -D eslint @eslint/js typescript-eslint prettier eslint-config-prettier`.
Division of labor: Prettier formats, ESLint lints. Never enable ESLint formatting rules;
`eslint-config-prettier` (last in the array) turns off any that conflict.

```js
// eslint.config.js
import js from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import tseslint from "typescript-eslint";
import eslintConfigPrettier from "eslint-config-prettier/flat";

export default defineConfig([
  globalIgnores(["dist/", "coverage/"]),
  {
    files: ["**/*.ts", "**/*.tsx"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommendedTypeChecked,
      tseslint.configs.stylisticTypeChecked,
    ],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
  },
  {
    files: ["**/*.js", "**/*.mjs", "**/*.cjs"],
    extends: [js.configs.recommended, tseslint.configs.disableTypeChecked],
  },
  eslintConfigPrettier,
]);
```

- Upgrade path: swap `recommendedTypeChecked` → `strictTypeChecked` once the baseline is
  clean.
- The `disableTypeChecked` block prevents typed-rule parse errors on plain-JS files
  (config files, scripts) not covered by a tsconfig.
- Do not rename the `@typescript-eslint` plugin key: `eslint-config-prettier` matches
  rules by their standard names.

```json
// .prettierrc.json — explicit even where these match current defaults
{
  "printWidth": 100,
  "tabWidth": 2,
  "useTabs": false,
  "semi": true,
  "singleQuote": false,
  "trailingComma": "all",
  "arrowParens": "always",
  "endOfLine": "lf"
}
```

Add a `.prettierignore` mirroring lint ignores (`dist/`, `coverage/`).

```jsonc
// package.json (scripts)
{
  "scripts": {
    "lint": "eslint . --max-warnings=0",
    "lint:fix": "eslint . --fix",
    "format": "prettier --write .",
    "format:check": "prettier --check ."
  }
}
```

## 5. Migration paths

### eslintrc → flat config (mandatory on ESLint v10)

1. Run the official migrator: `npx @eslint/migrate-config .eslintrc.json`
   (verify: https://eslint.org/docs/latest/use/configure/migration-guide).
   Caveat: for `.eslintrc.js` it emits the *evaluated* config — functions and
   conditionals are flattened to raw data; review and re-add logic by hand.
2. Fold `.eslintignore` into `globalIgnores([...])`; v10 ignores the file.
3. Delete every `.eslintrc.*` — with v10's file-relative config lookup, a stray legacy
   file silently does nothing, and a stray `eslint.config.js` in a subdirectory *wins*
   for files under it.
4. Expect the migrated output to need edits before it runs clean; it is a starting
   point, not a guaranteed equivalent.

### ESLint/Prettier → Biome

1. With `biome.json` initialized (`npx @biomejs/biome init`) and the old configs still
   present, run:
   `npx @biomejs/biome migrate eslint --write` and
   `npx @biomejs/biome migrate prettier --write`
   (verify: https://biomejs.dev/guides/migrate-eslint-prettier/).
2. `migrate eslint` reads legacy and flat configs and resolves plugins via Node; add
   `--include-inspired` to also map rules Biome reimplemented with deviations. YAML
   configs are not supported.
3. Behavior will not be byte-identical — Biome deviates on some rule options. Diff a
   full `biome check` run against the old ESLint output before deleting anything.
4. Enable `vcs.useIgnoreFile` (the old tools honored `.gitignore`; Biome only does with
   this on), remove ESLint/Prettier deps and configs, then reformat the whole repo in
   one dedicated commit.

## 6. Editor and CI wiring

VS Code — Biome stack (extension `biomejs.biome`; setting names: verify at use time,
https://biomejs.dev/guides/editors/first-party-extensions/):

```jsonc
// .vscode/settings.json
{
  "editor.defaultFormatter": "biomejs.biome",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "quickfix.biome": "explicit",
    "source.organizeImports.biome": "explicit"
  }
}
```

VS Code — ESLint+Prettier stack (`dbaeumer.vscode-eslint`, `esbenp.prettier-vscode`):

```jsonc
{
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": { "source.fixAll.eslint": "explicit" }
}
```

Commit `.vscode/settings.json` so the whole team gets identical on-save behavior.

CI rules:

- Fail on any warning: `eslint . --max-warnings=0`, or `biome ci --error-on-warnings .`.
  A warning that never fails a build is noise that trains people to ignore output.
- CI runs read-only commands (`--check`, `biome ci`) — never auto-fix in CI.
- Pin exact tool versions (`-E` / lockfile-committed) so local, editor, and CI agree;
  formatter drift between minor versions causes churn diffs.
- Run lint and format-check as separate named CI steps so failures are self-explaining.
- Pre-commit hooks (husky/lefthook + lint-staged) are optional comfort; CI is the
  authority. Hooks must run the same commands as CI, only on staged files.

## 7. Rule tuning: fix signal, not silence

- Default response to a diagnostic is to **fix the code**. Suppression is the exception
  and always carries a reason:
  - ESLint: `// eslint-disable-next-line rule-name -- why this is safe here`
  - Biome: `// biome-ignore lint/<group>/<rule>: why this is safe here` (reason
    syntactically required)
- Keep `linterOptions.reportUnusedDisableDirectives: "error"` (Section 4) so stale
  suppressions are removed automatically; Biome likewise reports suppression comments
  that no longer match a diagnostic (verify at use time).
- Disable a rule project-wide only when you can articulate why it is wrong *for this
  codebase*, and record that reason next to the override. "It was noisy" means the
  finding backlog was too big, not that the rule is wrong — use a ratchet instead:
  suppress existing hits (Biome v2 bulk suppressions; ESLint `--fix` plus scripted
  inline disables), keep the rule `error` for new code, burn down the backlog.
- Never widen `--max-warnings`; it only moves in one direction (toward 0, then stays).
- Scope exceptions by path, not globally: generated code, fixtures, and vendored files
  get their own `ignores`/`files.includes` entries rather than rule downgrades.
- When adopting stricter presets (`strictTypeChecked`, Biome `domains.types`), land the
  preset and the code fixes in the same PR series — a preset that sits half-suppressed
  for months is worse than not adopting it.
- Framework-specific rulesets (React hooks, Next.js) belong to their framework skill —
  for Next.js apps, hand off to `nextjs-quality` instead of tuning here.
