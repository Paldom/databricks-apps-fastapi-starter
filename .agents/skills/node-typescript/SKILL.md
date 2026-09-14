---
name: node-typescript
description: Configures TypeScript for Node libraries and apps - strict tsconfig, module and moduleResolution choices, verbatimModuleSyntax, isolatedDeclarations, declaration emit. Use when the user asks to set up TypeScript, tighten tsconfig, add a tsc type-check step that fails the build, or fix declaration output. Not for lint rules, bundling, or package exports.
license: MIT
argument-hint: [library|app|strictify]
---

# node-typescript

Produces TypeScript configurations that are **explicit, strict, and correct for
how the code is consumed**. The failures this skill fixes: models copy tsconfigs
whose implicit defaults changed between TypeScript majors, pick `bundler`
resolution for unbundled Node packages (broken for consumers), and flip strict
mode on a large codebase in one unreviewable big bang.

## When NOT to use

- Lint/format rules → `node-lint`.
- Bundling and `exports` maps / consumer type *resolution* → `node-packaging`
  (this skill owns declaration *emission*; the packaging skill owns how
  consumers resolve it).
- Test runner TS support → `node-testing`.

## Workflow

1. **Explicit-config principle first.** Never rely on generated or version
   defaults — TypeScript majors have changed them. Every option that matters is
   written out, per the blocks in `references/tsconfig-playbook.md`.
2. **Choose by consumption model**, not fashion:
   - Published/unbundled Node package → `module`/`moduleResolution` in the
     `nodenext` family; `verbatimModuleSyntax`; `declaration` +
     `declarationMap`; `isolatedDeclarations` where the API surface allows
     (parallel, tool-agnostic declaration emit).
   - Bundled app code → `bundler` resolution with `noEmit` (the bundler emits).
3. **Gate it**: `tsc --noEmit` (or `-b` for project references) as a script and
   a CI job (wiring → `node-ci`).
4. **Strictification of an existing codebase** is a ratchet, not a flip: measure
   the error surface first, enable flags incrementally (per-flag or
   per-directory), and keep CI green with a no-new-errors rule. Playbook has the
   sequence.
5. **Verify**: clean `tsc --noEmit`; for published packages, confirm declarations
   emit and hand consumer-resolution verification to `node-packaging`'s gates.

## Output spec

An explicit tsconfig with every load-bearing option stated; type-check script +
CI gate; for libraries: declarations emitting with maps; a written rationale for
module/resolution choices; strictification plan with measurable checkpoints when
applicable.

## Gotchas

- `bundler` resolution on a package consumed by Node directly will typecheck
  locally and break consumers — the consumption model decides, always.
- `verbatimModuleSyntax` makes `import type` mandatory for type-only imports and
  constrains CJS-emit default exports — enable it *with* the codemod pass.
- `isolatedDeclarations` demands explicit return types on exported API — great
  for libraries, noisy for apps; don't cargo-cult it into app configs.
- TypeScript 7 (the native compiler, GA July 2026) is what `typescript@latest`
  installs; explicit tsconfigs stay compatible, but 6.0's deprecations
  (`baseUrl`, `target: es5`, `moduleResolution: classic`) are hard errors on 7 —
  the playbook lists them and the `@typescript/typescript6` fallback for
  API-dependent tooling.
- Version-gate: re-verify default/flag behavior against the official TSConfig
  reference when the TS major changes.

## Files

- `references/tsconfig-playbook.md` — explicit config blocks (library/app),
  nodenext-vs-bundler decision, strictification ratchet, verification commands.
