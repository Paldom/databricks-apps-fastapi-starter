# tsconfig Playbook — Configuration and Type-Check Gates

Scope: TypeScript compiler configuration and CI type-check gates.
NOT in scope: lint rules (ESLint config lives in the linting reference), bundler
configuration, and `package.json` `exports` / types-resolution for consumers —
those belong to the sibling **node-packaging** skill.

## Contents

- [Principle: explicit config, never defaults](#principle-explicit-config-never-defaults)
- [Config A — published Node library](#config-a--published-node-library)
- [Config B — bundled application](#config-b--bundled-application)
- [Choosing `nodenext` vs `bundler`](#choosing-nodenext-vs-bundler)
- [CI type-check gate](#ci-type-check-gate)
- [Incremental strictification playbook](#incremental-strictification-playbook)
- [Publishing types: declaration emit basics](#publishing-types-declaration-emit-basics)
- [tsgo / TypeScript 7 status](#tsgo--typescript-7-status)

## Principle: explicit config, never defaults

Write every load-bearing compiler option explicitly. Never rely on what a flag
"defaults to" or on a generated `tsconfig.json`, because both change across
TypeScript versions. The configs in this playbook set every load-bearing option
explicitly, so no default is load-bearing here — the notes below are advisory
context on *why* omission is unsafe, not facts your config should lean on:

- TypeScript 6.0 (released March 2026) flipped several implicit defaults:
  `strict` is now `true` by default, `module` defaults to `esnext`, `target`
  floats with the latest supported ECMAScript version (`es2025` at release),
  `types` defaults to `[]` instead of "every `@types/*` package", `rootDir`
  defaults to the tsconfig directory instead of being inferred, and
  `noUncheckedSideEffectImports` defaults to `true`. A config that "worked" by
  omission on 5.x means something different on 6.x — as of mid-2026 (verify:
  https://www.typescriptlang.org/docs/handbook/release-notes/typescript-6-0.html).
- `tsc --init` output was overhauled (slimmed and made more prescriptive) in
  5.9. Treat generated files as a starting sketch, not a contract (verify:
  https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-9.html).
- TypeScript 6.0 also retires legacy options (verify: the 6.0 release notes
  above): `moduleResolution: "node10"`, `target: "es5"`, `baseUrl`,
  `module: "amd"/"umd"/"system"`, `moduleResolution: "classic"`, and disabling
  `esModuleInterop` / `allowSyntheticDefaultImports` are **deprecated** — they
  still work on 6.x with `"ignoreDeprecations": "6.0"`; only `outFile` is
  removed outright in 6.0. TypeScript 7.0 turns those deprecations into hard
  errors (see the status section below). Do not put deprecated options in new
  configs.

Rules that follow from this:

1. Set `strict`, `module`, `moduleResolution`, `target`, `lib`, `types`,
   `rootDir`/`outDir` (when emitting), and `skipLibCheck` explicitly in every
   repo — even when your value matches the current default.
2. Pin the `typescript` version exactly in `devDependencies` (no `^`), and
   upgrade it as a deliberate PR that re-reads the release notes.
3. When a claim about a flag's behavior matters, check it against
   https://www.typescriptlang.org/tsconfig/ rather than memory.

## Config A — published Node library

Use this for an npm package that ships compiled JS + `.d.ts` and is resolved by
Node (not pre-bundled by the consumer's bundler).

```jsonc
// tsconfig.json — published Node library
{
  "compilerOptions": {
    // Module system: Node-faithful resolution and emit
    "module": "nodenext",
    "moduleResolution": "nodenext",   // implied by module=nodenext; state it anyway
    "verbatimModuleSyntax": true,
    "esModuleInterop": true,          // disabling is deprecated in 6.0, an error in 7.0; keep explicit
    "isolatedModules": true,

    // Language level — pin per your minimum supported Node; do NOT float with
    // the compiler default. Check your floor at use time against
    // https://www.typescriptlang.org/tsconfig/target.html and node.green.
    "target": "es2023",
    "lib": ["es2023"],
    "types": ["node"],                // only what you actually use; never omit

    // Emit
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "outDir": "dist",
    "rootDir": "src",

    // Strictness
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true,
    "isolatedDeclarations": true,     // see caveat below

    // Hygiene
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true              // deliberate choice: don't re-check dependency d.ts
  },
  "include": ["src"]
}
```

Why these flags:

- `module`/`moduleResolution: "nodenext"` — makes `tsc` enforce Node's real ESM
  rules (file extensions in relative imports, `package.json` `"type"`,
  conditional exports). Code that passes under `nodenext` also works under
  bundlers; the reverse is not true. Prefer `nodenext` (floating) for
  libraries; `node20`/`node18` are the pinned equivalents if you need stable
  behavior across compiler upgrades.
- `verbatimModuleSyntax: true` — official recommendation for libraries: bans
  imports whose meaning depends on the *consumer's* `esModuleInterop`/
  `allowSyntheticDefaultImports`, and blocks `export default` in files that
  emit as CommonJS (verify:
  https://www.typescriptlang.org/docs/handbook/modules/guides/choosing-compiler-options.html).
- `isolatedDeclarations: true` — changes *error reporting only*: every export
  must be annotated well enough that `.d.ts` can be produced without the type
  checker, which keeps your public API explicit and enables fast/parallel
  declaration emit in external tools. It is demanding (explicit return types on
  all exports): use it where the API surface allows the annotation burden, and
  verify the flag's status for the installed TypeScript major before relying on
  it (https://www.typescriptlang.org/tsconfig/isolatedDeclarations.html). If
  the burden is too high for an existing codebase, drop this one flag and keep
  the rest.
- `noUncheckedIndexedAccess: true` — makes `arr[i]` / index-signature reads
  `T | undefined`. Highest-value strictness flag outside the `strict` family;
  not included in `strict` (verify:
  https://www.typescriptlang.org/tsconfig/noUncheckedIndexedAccess.html).
- `declaration` + `declarationMap` + `sourceMap` — required for a publishable
  library; `declarationMap` gives consumers go-to-source in editors.
- `skipLibCheck: true` — skips re-type-checking dependency `.d.ts` files. This
  is a tradeoff (it can mask broken upstream types); set it explicitly either
  way so a version bump never flips it silently.

## Config B — bundled application

Use this when a bundler (esbuild, Vite, tsup, webpack, etc.) produces the
runtime output and `tsc` exists only as the type-check gate. The block below is
the Node-side shape; a browser/React app additionally needs `"lib": ["es2023",
"dom", "dom.iterable"]`, `"jsx": "react-jsx"`, and the framework's client types
(e.g. `"types": ["vite/client"]`) — keep whatever the framework scaffold
generated for those and only tighten the strictness flags.

```jsonc
// tsconfig.json — bundled app: tsc type-checks, the bundler emits
{
  "compilerOptions": {
    // Module system: match what the bundler resolves
    "module": "esnext",               // or "preserve" if you mix import/require
    "moduleResolution": "bundler",
    "verbatimModuleSyntax": true,
    "esModuleInterop": true,
    "isolatedModules": true,          // one-file-at-a-time transpilers need this

    "target": "es2023",               // pin to your runtime floor; do not float
    "lib": ["es2023"],
    "types": ["node"],

    // No emit — the bundler owns output
    "noEmit": true,

    // Strictness (same bar as the library config)
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true,

    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

Notes:

- `noEmit: true` — never let both `tsc` and the bundler write output; two
  emitters drift.
- `isolatedModules: true` is mandatory when a non-type-aware transpiler
  (esbuild, swc) does the emit — it errors on constructs that need cross-file
  type information.
- Do not add `paths` aliases that the bundler cannot also resolve; keep `tsc`
  and bundler resolution in lockstep. (`baseUrl` is deprecated in 6.0 — write
  prefixes directly in `paths` entries.)

## Choosing `nodenext` vs `bundler`

Decision rule (matches the official modules guidance; verify:
https://www.typescriptlang.org/docs/handbook/modules/guides/choosing-compiler-options.html):

- **Output is run by Node directly** (published library, unbundled server/CLI):
  `module: "nodenext"` + `moduleResolution: "nodenext"`. Node's rules are the
  strictest; passing them means bundlers work too.
- **Output is produced by a bundler**: `moduleResolution: "bundler"` with
  `module: "esnext"` (or `"preserve"`). Mirrors bundler behavior:
  extension-less relative imports, `exports` conditions like `"module"`.
- **Never** use `bundler` resolution for code that Node will load unbundled —
  it accepts imports Node will reject at runtime. `bundler` is infectious:
  it lets you produce code that only works under bundlers.
- Dual-published library that consumers may bundle? Still `nodenext` — that is
  the portable superset. How the *package* exposes CJS/ESM entry points is an
  `exports`-map question: sibling **node-packaging**.

## CI type-check gate

Make type-checking a standalone, required CI step — separate from build, lint,
and test, so failures are attributable:

```yaml
# .github/workflows/ci.yml (excerpt)
typecheck:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v7
    - uses: actions/setup-node@v7
      with: { node-version: 22, cache: npm }
    - run: npm ci
    - run: npx tsc -p tsconfig.json --noEmit
```

- Always pass `-p <config>` explicitly; never rely on cwd discovery.
- For a library that emits, keep the gate as `tsc --noEmit` against the same
  config, and do the emitting build (`tsc -p tsconfig.json`) in the
  build/publish job. One config, two invocations — avoid drift.
- Type-check tests too: either `include` test files in the gate config or run a
  second `tsc -p tsconfig.test.json --noEmit`. Untyped tests rot first.
- Monorepos with project references: `npx tsc -b --noEmit` (build mode walks
  the reference graph). Note `--noEmit` with `-b` requires composite projects
  to still write `.tsbuildinfo` — verify current interaction at use time
  against https://www.typescriptlang.org/docs/handbook/project-references.html.
- The `typescript` version in the lockfile is the gate's spec. Pin exact;
  upgrade deliberately.

## Incremental strictification playbook

For an existing codebase that cannot turn everything on at once. Two mechanisms:
a **per-flag ratchet** (which flags, in what order) and a **no-new-errors gate**
(so the count only goes down).

Per-flag ratchet — enable one flag at a time, in payoff order:

1. `noImplicitAny` — biggest win, catches missing annotations at boundaries.
2. `strictNullChecks` — biggest diff; do it as its own campaign.
3. Rest of the `strict` family (`strictFunctionTypes`,
   `strictBindCallApply`, `strictPropertyInitialization`,
   `useUnknownInCatchVariables`, `noImplicitThis`, `alwaysStrict`) — then
   replace the list with `strict: true`.
4. Post-strict extras: `noUncheckedIndexedAccess`,
   `exactOptionalPropertyTypes`, `noImplicitOverride`,
   `noFallthroughCasesInSwitch`, `isolatedDeclarations` (libraries).

Mechanics:

- Keep `tsconfig.json` at the level the whole repo passes. Add
  `tsconfig.strict.json` that `extends` it and adds the next target flag:

```jsonc
// tsconfig.strict.json — the ratchet target
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "noUncheckedIndexedAccess": true   // current campaign flag
  }
}
```

- Gate CI on a committed error-count baseline that can only shrink:

```bash
#!/usr/bin/env bash
# scripts/type-ratchet.sh — no-new-errors gate (count is a proxy; see note below)
set -uo pipefail
baseline=$(cat .tsc-error-baseline)          # committed integer
out=$(npx tsc -p tsconfig.strict.json --noEmit --pretty false 2>&1); status=$?
count=$(printf '%s\n' "$out" | grep -cE 'error TS[0-9]+' || true)
# tsc exits 0 only when clean; a non-zero exit with zero diagnostics means tsc
# itself failed (missing inputs, bad config, not installed) — never count that as 0.
if [ "$status" -ne 0 ] && [ "$count" -eq 0 ]; then
  printf '%s\n' "$out"; echo "tsc did not run to completion — not a green ratchet."; exit 1
fi
echo "strict-candidate errors: $count (baseline $baseline)"
if [ "$count" -gt "$baseline" ]; then
  echo "New type errors introduced under the ratchet config. Fix or annotate."; exit 1
fi
if [ "$count" -lt "$baseline" ]; then
  echo "Baseline can drop to $count — update .tsc-error-baseline in this PR."; exit 1
fi
```

A count can hide one fixed error traded for one new one; when that matters,
diff the normalized diagnostics (`file:TScode`) against a committed list
instead. The baseline is updated by a human in the PR that earns it, never by
CI writing to the tree.

- When suppressing a pre-existing error to unblock a file, use
  `// @ts-expect-error TODO(strict): <reason>` — never `@ts-ignore` — so
  suppressions self-destruct when the underlying error is fixed and are
  greppable for the campaign.
- When the count hits 0, move the flag into `tsconfig.json`, reset the
  baseline, and pick the next flag. Dedicated baseline tools exist in the
  ecosystem; evaluate at use time rather than by name here.

## Publishing types: declaration emit basics

What belongs in the compiler config (this file):

- `declaration: true` and `declarationMap: true` in the library config; ship
  the resulting `.d.ts` and `.d.ts.map` files in the published package (and the
  source files if you want `declarationMap` navigation to work for consumers).
- If you only need types (emit handled elsewhere), use
  `emitDeclarationOnly: true` alongside `declaration: true`.
- Under `isolatedDeclarations`, declaration output is a syntactic transform of
  your annotated source — keep exports explicitly typed and emit stays fast and
  tool-agnostic.

What does NOT belong here: how consumers *resolve* those types — the
`package.json` `"types"` field, `exports` conditions (`"types"`,
`"import"`/`"require"`), dual-package `.d.cts`/`.d.mts` layout, and validators
like publint/arethetypeswrong. All of that is the sibling **node-packaging**
reference; route there.

## tsgo / TypeScript 7 status

As of September 2026: **TypeScript 7.0 is GA** (2026-07-08) and is what
`npm install -D typescript` installs — the `tsc` binary *is* the native Go
compiler, reported as often about 10x faster, with type-checking and CLI
behavior made compatible with 6.0. TypeScript 6.0 (March 2026) is the last
release built on the JavaScript codebase and stays supported as the fallback.
What 7.0 makes hard errors (6.0 only deprecated them, and `ignoreDeprecations:
"6.0"` no longer exists as an escape hatch): `target: "es5"` and
`downlevelIteration`, `baseUrl` (fold the prefix into `paths` targets),
`moduleResolution: "node"/"node10"/"classic"` (use `nodenext` or `bundler`),
`module: "amd"/"umd"/"systemjs"/"none"` and `outFile`, `esModuleInterop:
false` / `allowSyntheticDefaultImports: false` / `alwaysStrict: false`, the
`module` keyword for namespaces, and `assert { type: "json" }` (use `with`).
Defaults that changed for configs that omit them: `strict` and
`noUncheckedSideEffectImports` → `true`, `module` → `esnext`, `types` → `[]`
(list `["node"]` etc. explicitly), `rootDir` → the tsconfig directory (add
`"rootDir": "./src"` if emit paths shift), `stableTypeOrdering` → `true` and
not switchable. `tsc file.ts` next to a tsconfig now needs `--ignoreConfig`.
Dual-install pattern for tooling that still needs the 6.x API: alias
`"typescript": "npm:@typescript/typescript6@^6.0.2"` (ships `tsc6`) and
`"@typescript/native": "npm:typescript@^7.0.2"` for the real `tsc` — and note
editors then resolve through the 6.x alias, so a type native 7 rejects can
still look green in the IDE; CI on native 7 is the signal. Key caveat: a stable programmatic
compiler API is not planned before TypeScript 7.1, so API-dependent tooling
(type-aware lint plugins, custom transformers, some editor integrations) may
need the `@typescript/typescript6` compatibility package in the interim.
Nightlies now ship as `typescript@next` (7.1-dev); the `@typescript/native-preview`
package (binary `tsgo`) is frozen at the 7.0 dev builds. Verify at use time:
https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/ and
https://github.com/microsoft/typescript-go. The tsconfig blocks above avoid
everything 6.0 deprecated, so they are valid on 7.x as written.
