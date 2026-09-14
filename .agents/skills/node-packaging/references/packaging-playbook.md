# npm Packaging Playbook

Build correct, verifiable npm package artifacts: module format decision, `exports`
maps, bundling, and publish-readiness gates.

**Scope:** package artifacts only.
- Declaration-file EMIT strategy (tsc config, isolatedDeclarations) -> `node-typescript`.
- Version bumps, changelogs, tags, `npm publish`, provenance -> `node-release`.
- Registry auth/tokens -> out of scope for this skill.

## Contents

1. [Decide the format: ESM-first, not ESM-only-always](#1-decide-the-format-esm-first-not-esm-only-always)
2. [Exports maps](#2-exports-maps)
3. [Dual-package hazard](#3-dual-package-hazard)
4. [Bundling: tsdown (tsup is unmaintained)](#4-bundling-tsdown-tsup-is-unmaintained)
5. [package.json fields that gate publish quality](#5-packagejson-fields-that-gate-publish-quality)
6. [Publish-readiness gates](#6-publish-readiness-gates)
7. [Pre-publish checklist](#7-pre-publish-checklist)

---

## 1. Decide the format: ESM-first, not ESM-only-always

Author in ESM. Whether you *ship* ESM-only or dual ESM+CJS depends on which Node
versions your consumers run, because modern Node lets CJS consumers `require()`
your ESM directly — removing the main historical reason to ship CJS.

### require(esm) support matrix

As of mid-2026 (verify: https://nodejs.org/api/modules.html#loading-ecmascript-modules-using-require):

| Node line | `require(esm)` | Notes |
|---|---|---|
| 20.x | Unflagged from 20.19.0 | Line is **EOL** (2026-04-30) |
| 22.x | Unflagged from 22.12.0; warning-free from 22.13.0 | Maintenance LTS until 2027-04 |
| 24.x | Unflagged, warning-free | Active LTS |
| 26.x | Stable (marked non-experimental in 25.4.0) | Current |
| < 20.19, < 22.12 | **No** (flag required or absent) | Ship CJS if you support these |

Release-line status above is as of mid-2026 (verify: https://github.com/nodejs/Release).

**Hard constraint:** `require()` can only load *fully synchronous* ES module graphs.
Any top-level `await` anywhere in the required graph (including your dependencies'
ESM you re-export) throws `ERR_REQUIRE_ASYNC_MODULE`. Audit before going ESM-only:
grep your dist output and re-exported deps for top-level `await`; debug with
`node --experimental-print-required-tla` (verify flag at use time).

### Decision procedure

1. Set `"engines": { "node": ">=X" }` from actual consumer reality, not aspiration.
2. If `engines` guarantees `>=20.19` (practically: `>=22.12` now that 20 is EOL)
   AND your module graph has no top-level await -> **ship ESM-only**. CJS
   consumers `require()` it directly.
3. If you must support older Node lines or Electron/bundler matrices you cannot
   verify -> **ship dual ESM+CJS** and manage the dual-package hazard (section 3).
   Top-level `await` is **not** solved by a format choice: CommonJS cannot express
   it, so a CJS build of a graph with TLA fails or deadlocks. Either remove the
   TLA (lazy/async init behind a function) so `require(esm)` works, or stay
   ESM-only and document that CJS consumers must `import()` — test the
   transitive graph, TLA in a dependency counts too.
4. Never ship CJS-only for new packages.

**CJS interop polish (ESM-only packages):** when `require()` loads your ESM, CJS
consumers get a namespace object (`{ default, ...named, __esModule: true }`). To
make `const X = require('your-pkg')` return the default export directly, add the
`'module.exports'` interop export (supported from Node 22.12/23.0; verify:
https://nodejs.org/api/modules.html#loading-ecmascript-modules-using-require):

```js
export default class Point { /* ... */ }
export { Point as 'module.exports' };
// Caveat: named exports are then invisible to require(); attach them as
// static properties of the default export if CJS consumers need them.
```

## 2. Exports maps

Rules that apply to every map:

- Always define `"exports"` (it encapsulates the package: unlisted paths are
  unreachable). Add `"main"` only as a legacy fallback for pre-exports tooling.
- Conditions match in **object key order**; put `"types"` **first** inside each
  branch and `"default"` **last** (verify: https://nodejs.org/api/packages.html#community-conditions-definitions
  and https://www.typescriptlang.org/docs/handbook/modules/reference.html#packagejson-exports).
- Expose `"./package.json": "./package.json"` — many tools read it.
- Every published entry point gets its own subpath; do not rely on directory access.

### ESM-only package (full explicit config)

```jsonc
{
  "name": "your-pkg",
  "type": "module",
  "engines": { "node": ">=22.12" },
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    },
    "./advanced": {
      "types": "./dist/advanced.d.ts",
      "default": "./dist/advanced.js"
    },
    "./package.json": "./package.json"
  }
}
```

One `.d.ts` per entry is sufficient here: there is only one module format.

### Dual ESM+CJS package (full explicit config)

Each format condition needs its **own** declaration file — `.d.ts` (or `.d.mts`)
for the `import` branch, `.d.cts` for the `require` branch. A single shared
`.d.ts` under both branches is the classic "masquerading" failure that
arethetypeswrong flags (verify current guidance:
https://github.com/arethetypeswrong/arethetypeswrong.github.io and
https://www.typescriptlang.org/docs/handbook/modules/reference.html).

```jsonc
{
  "name": "your-pkg",
  "type": "module",
  "engines": { "node": ">=18" },        // floor below 20.19 is the reason this ships dual
  "main": "./dist/index.cjs",           // legacy-resolver fallback only
  "exports": {
    ".": {
      "import": {
        "types": "./dist/index.d.ts",   // ESM types ("type": "module" => .d.ts is ESM)
        "default": "./dist/index.js"
      },
      "require": {
        "types": "./dist/index.d.cts",  // CJS types — separate file, not a copy-only rename
        "default": "./dist/index.cjs"
      }
    },
    "./package.json": "./package.json"
  }
}
```

Declaration files must be *emitted* per-format, not hand-renamed (renaming alone
leaves `import`-flavored types describing a CJS file, or vice versa). tsdown
emits declarations per output format (section 4) — verify the emitted extensions
match your exports map (the attw gate in section 6 catches mismatches); how to
configure tsc itself for declaration emit -> `node-typescript`.

**Top-level fields vs `exports`:** when `exports` is present, modern resolvers
(Node, and TypeScript under `node16`/`nodenext`/`bundler`) resolve through it
and ignore top-level `main`/`module`/`types` for that purpose. A top-level
`"types"` field is still a legitimate *fallback* for TypeScript's legacy
`node10` resolution and tools that don't read `exports` — if you keep one,
point it at the root entry's declarations. Prefer `"types"` over its legacy
alias `"typings"`. A top-level `"module"` field is a non-standard bundler-only
convention Node never reads; with an `exports` map it is redundant for modern
bundlers — add it only for a documented old-bundler requirement. (Verify:
https://www.typescriptlang.org/docs/handbook/modules/reference.html#packagejson-exports)

## 3. Dual-package hazard

Shipping both formats means Node can load **two separate module instances** of
your package in one process (ESM copy via `import`, CJS copy via `require`,
e.g. through transitive deps). `instanceof` checks, singletons, module-level
caches, and registries silently break across the two copies.
(Verify: https://nodejs.org/api/packages.html#dual-package-hazard)

Mitigate, in order of preference:

1. **Ship ESM-only** when the support matrix allows (section 1) — hazard gone.
2. **Stateless wrapper:** make one format the real implementation and the other
   a thin re-export wrapper, so state lives in exactly one module instance.
3. If both artifacts must be real: keep the package stateless (no module-level
   mutable state, no `instanceof` across API boundaries).

## 4. Bundling: tsdown (tsup is unmaintained)

As of mid-2026, tsup's own README says it "is not actively maintained anymore"
and recommends **tsdown** (Rolldown-based, an official Rolldown project) as the
replacement (verify: https://github.com/egoist/tsup and https://tsdown.dev).
tsdown 0.23 (2026-09-03) bundles an attw "profile" check; its release notes say the
default profile is now `esm-only` (ignores CJS resolution failures) while the docs
still say `strict` — set `attw: { profile: "strict", level: "error" }` yourself if
CommonJS consumers matter, and keep running `arethetypeswrong` on the packed
tarball (the bundled gate does). tsup 8.5.1 is actively broken for TS 6/7
declaration builds (it injects `baseUrl: "."` during DTS generation → `TS5101`,
and `ignoreDeprecations` no longer exists on 7) — a hard reason to migrate.
Use tsdown for new packages; migrate existing tsup configs via its
"Migrate from tsup" guide (https://tsdown.dev/guide/migrate-from-tsup).

Explicit config — tsdown's defaults are reasonable (ESM output, `target` read
from `engines.node`, runtime deps externalized), but state the contract in the
config so the build doesn't change when defaults do:

```ts
// tsdown.config.ts
import { defineConfig } from 'tsdown'

export default defineConfig({
  entry: ['src/index.ts'],       // one entry per exports subpath
  format: ['esm'],               // dual: ['esm', 'cjs'] — emits .js + .cjs and matching dts
  dts: true,                     // emit declarations per format
  platform: 'node',              // the default; 'neutral' for runtime-agnostic code
  target: 'node20.19',           // match your engines floor (ESM-only needs >=20.19;
                                 // dual for older lines: e.g. 'node18'). When omitted,
                                 // tsdown reads engines.node from package.json.
  clean: true,
  sourcemap: true,
})
```

Dependency handling: tsdown externalizes `dependencies`, `peerDependencies`,
and `optionalDependencies` by default — do not set `external` to (re)state
that. To force-bundle a specific dep, use `deps.alwaysBundle`; to force-exclude,
`deps.neverBundle` (the older `noExternal`/`external` options are deprecated
aliases). As of mid-2026 (verify: https://tsdown.dev/options/dependencies).
Verify exact option names against https://tsdown.dev/options at use time.

Bundling policy for libraries:

- Keep `dependencies` external (tsdown's default, installed by the consumer);
  force-bundle only with a concrete reason (patching, size-critical CLI).
- `devDependencies` used at runtime is a publish bug — publint flags it.
- CLIs may fully bundle; add the shebang via the entry file, mark `"bin"`.
- Do not minify library output; consumers' bundlers do that.

## 5. package.json fields that gate publish quality

```jsonc
{
  // Whitelist > .npmignore. Only these ship (plus package.json, README, LICENSE).
  "files": ["dist"],

  // Contract for consumers AND the input to the ESM-only decision (section 1).
  "engines": { "node": ">=22.12" },

  // Pins the maintainer toolchain. Note: Corepack, which enforces this field,
  // is bundled with Node <= 24 but removed from Node 25+ distributions —
  // install it separately or rely on your PM's own check.
  // As of mid-2026 (verify: https://github.com/nodejs/corepack).
  "packageManager": "pnpm@12.3.4",

  // Bundler tree-shaking hint (webpack et al.). `false` = safe to drop unused
  // modules. List exceptions explicitly if any module has import side effects
  // (polyfills, CSS). Wrong `false` => consumers silently lose code.
  // Verify semantics: https://webpack.js.org/guides/tree-shaking/
  "sideEffects": false,

  "publishConfig": { "access": "public" }   // scoped packages default to restricted
}
```

`files` gotchas: patterns are relative to package root; `dist` includes the whole
directory; test fixtures inside `dist` still ship — inspect the tarball (below).

## 6. Publish-readiness gates

Run all three gates in CI against the **same packed tarball**, not the working
tree: pack once with `npm pack --json`, then point publint and attw at that
tarball. The bundled `scripts/check_package.sh` does exactly this and exits
non-zero on any finding.

### Gate 1 — inspect the artifact

```sh
npm pack --dry-run                                    # human-readable file list + size
npm pack --json --pack-destination "$TMP" > pack.json # real pack: tarball + JSON file list
```

Assert on the JSON `files` list (grepping the human `npm notice` output is not
reliable). Reject if: missing `dist` files, leaked `src`/tests/`.env`/maps you
didn't intend, or surprising unpacked size.

### Gate 2 — publint (package.json vs artifact consistency)

```sh
npx publint --strict ./your-pkg-1.0.0.tgz   # lint the exact tarball from Gate 1
npx publint --strict                        # convenience: pack + lint current directory
```

`--strict` reports warnings as errors.

Catches: exports pointing at missing files, format mismatches (`.js` that is
CJS under `"type": "module"`), invalid `files`, legacy-field inconsistencies.
Commands as of mid-2026 (verify: https://publint.dev/docs/cli).

### Gate 3 — arethetypeswrong (types resolve under every resolver)

```sh
attw your-pkg-1.0.0.tgz                       # analyze the same tarball from Gate 1
npx @arethetypeswrong/cli --pack .            # convenience: pack cwd and analyze
npx @arethetypeswrong/cli --pack . --profile esm-only   # ESM-only packages
attw --from-npm your-pkg                      # audit what's already published
```

Fails on: false-CJS/false-ESM masquerading, missing `types` per condition,
unresolvable subpaths under `node16`/`bundler` resolution. Persist options in
`.attw.json`. Commands as of mid-2026 (verify:
https://github.com/arethetypeswrong/arethetypeswrong.github.io/tree/main/packages/cli).

### Wire as scripts

```jsonc
{
  "scripts": {
    "build": "tsdown",
    "check:package": "publint --strict && attw --pack .",
    "prepack": "npm run build"
  },
  "devDependencies": {
    "publint": "latest-pinned-at-use-time",
    "@arethetypeswrong/cli": "latest-pinned-at-use-time",
    "tsdown": "latest-pinned-at-use-time"
  }
}
```

Note: in this convenience form each tool packs its own tarball. The canonical
gate is `scripts/check_package.sh`, which packs once (`npm pack --json`), then
runs the file-list assertion, `publint --strict`, and attw against that single
artifact. Pin real versions at use time; run the gate in CI on every PR
touching `package.json`, build config, or entry points.

## 7. Pre-publish checklist

1. Format decision recorded: ESM-only justification (engines floor, no top-level
   await in required graph) or dual + hazard mitigation (section 3).
2. `exports` map explicit: `types` first per branch, `default` last,
   `./package.json` exposed; top-level `types` only as a deliberate legacy
   fallback, no `typings` alias, no `module` field without a documented need.
3. Dual only: separate emitted `.d.ts` + `.d.cts`, not renamed copies.
4. `files` whitelist present; `npm pack --dry-run` output reviewed.
5. `engines`, `packageManager`, `sideEffects`, `publishConfig.access` set explicitly.
6. `publint --strict` and attw clean against the same packed tarball
   (`scripts/check_package.sh`; intentional, documented `--ignore-rules` only).
7. README + LICENSE included in tarball.
8. Then hand off: version bump, changelog, tag, `npm publish`, provenance ->
   `node-release`.
