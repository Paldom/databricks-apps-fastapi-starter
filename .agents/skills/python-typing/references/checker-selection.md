# Choosing a Python type checker (2026 — an unsettled race)

**Contents:** [State of the race](#state-of-the-race) ·
[The contenders](#the-contenders) · [Comparison table](#comparison-table) ·
[Decision guide](#decision-guide) · [The hybrid pattern](#the-hybrid-editorci-pattern) ·
[Multi-checker CI](#multi-checker-ci-know-the-cost) ·
[Claims not to repeat](#claims-not-to-repeat-as-fact) · [Sources](#sources)

## State of the race

Unlike linting (settled on Ruff), static typing is a genuinely contested
layer. mypy and pyright are the two mature incumbents; a newer generation of
Rust-based checkers (Astral's ty, Meta's Pyrefly, the solo-maintained zuban)
competes on speed. Community debate is active and unresolved — recommend per
situation, not a universal winner, and expect the answer to shift; re-evaluate
at each project milestone rather than hard-coding a choice into team dogma.

## The contenders

- **mypy** ([github.com/python/mypy](https://github.com/python/mypy)) — the
  reference implementation, written in Python (mypyc-compiled). Slowest of the
  field but the only one with a **plugin system**: Django (`django-stubs`),
  SQLAlchemy, and Pydantic (`pydantic.mypy`) ship plugins that understand
  metaprogramming no stub-driven checker can. Defining quirk: it skips
  unannotated function bodies unless `check_untyped_defs`/`strict` is set.
- **pyright** ([github.com/microsoft/pyright](https://github.com/microsoft/pyright))
  — Microsoft, written in TypeScript, the engine behind VS Code's Pylance.
  Checks all code by default with aggressive inference; widely regarded as the
  closest to the typing spec. No plugins — stub-driven only. It is a Node.js
  program; the PyPI `pyright` package wraps it so `uv add --dev pyright` works
  in pure-Python environments.
- **basedpyright** ([github.com/DetachHead/basedpyright](https://github.com/DetachHead/basedpyright))
  — community fork of pyright that restores LSP features Microsoft reserves
  for closed-source Pylance (useful in Neovim, Helix, Emacs, Cursor), ships
  stricter defaults (its "recommended" preset enables all rules — stricter
  than either mypy or pyright), and friendlier CLI output. Configured via
  `[tool.basedpyright]`.
- **ty** ([github.com/astral-sh/ty](https://github.com/astral-sh/ty)) — from
  Astral (Ruff, uv), Rust, formerly Red Knot, in beta. Built around a formal
  "gradual guarantee": loosening or removing annotations in working code is designed never to
  introduce new errors elsewhere — a structural answer to the cascading-error
  pain ratchet strategies exist to manage. No plugin system. Config in
  `[tool.ty]` or `ty.toml`.
- **Pyrefly** ([pyrefly.org](https://pyrefly.org/),
  [github.com/facebook/pyrefly](https://github.com/facebook/pyrefly)) — Meta,
  Rust, built for very large monorepos. Opposite philosophy to ty: aggressive
  inference on untyped code by default, plus a `suppress` command that
  bulk-inserts suppressions across legacy code so strictness can be enabled
  immediately and debt cleaned up over time. Shipped experimental **Pydantic
  integration** ([pyrefly.org/blog/pyrefly-pydantic](https://pyrefly.org/blog/pyrefly-pydantic))
  — notable because no other stub-driven checker understands Pydantic models
  without a plugin.
- **zuban** — solo-maintained Rust checker with a "mypy mode" that reads
  existing mypy config files as-is; interesting for drop-in speed experiments
  on mypy-configured repos, with the bus-factor caveat a solo project carries.

## Comparison table

| Checker | Maintainer | Maturity | Plugins | Default posture | Config |
| --- | --- | --- | --- | --- | --- |
| mypy | Python community | Reference impl., most mature (2.x since 2026-05; 2.0 flipped `local-partial-types`/`strict-bytes` on) | Django, SQLAlchemy, Pydantic | Permissive — skips unannotated defs | `[tool.mypy]` / `mypy.ini` |
| pyright | Microsoft | Mature, editor-dominant | None | Checks everything, strong inference | `[tool.pyright]` / `pyrightconfig.json` |
| basedpyright | Community fork | Actively maintained | None | Stricter than pyright | `[tool.basedpyright]` |
| ty | Astral | Beta (0.0.x releases, pre-1.0 as of 2026-09) | None | Gradual guarantee, lenient on untyped | `[tool.ty]` / `ty.toml` |
| Pyrefly | Meta | Stable 1.x (1.2.0, 2026-08) | None | Aggressive inference + bulk suppress | `[tool.pyrefly]` / `pyrefly.toml` |
| zuban | Solo maintainer | Young | None (reads mypy config) | mypy-compatible mode | mypy config files |

## Decision guide

| Situation | Recommendation |
| --- | --- |
| Django / SQLAlchemy / Pydantic-heavy codebase | mypy as the CI gate — the plugins are load-bearing; add pyright/Pylance in-editor |
| New library, VS Code team | pyright `standard`, ratchet to `strict`; ship `py.typed` from day one |
| Neovim / Helix / Emacs / Cursor editors | basedpyright |
| Already on uv + Ruff, tolerant of beta churn | pilot ty for local/editor speed; keep mypy or pyright as the CI gate until it matures |
| Multi-million-LOC monorepo | evaluate Pyrefly |
| Existing mypy config, curious about speed | zuban's mypy mode as a low-cost experiment |
| Publishing a library for external consumers | whatever you gate on, smoke-test the public API with both mypy **and** pyright — downstream users run both |

## The hybrid editor/CI pattern

The de-facto community standard: **pyright/Pylance in the editor** for
instant feedback, **one authoritative checker in CI** as the merge gate
(mypy where plugins matter, pyright otherwise). The editor checker is
advisory; only the CI checker's config is the contract. This gets fast
feedback without dual-suppression bloat, because you only *silence* the gate
checker.

## Multi-checker CI — know the cost

Some projects run two or more checkers in CI and treat disagreement as a
quality signal (documented example: IBM's mcp-context-forge,
[github.com/IBM/mcp-context-forge/issues/211](https://github.com/IBM/mcp-context-forge/issues/211)).
It does catch more edge cases — the engines genuinely disagree on `**kwargs`
typing, `__new__` inference, and union widening (see
[pyright discussion #5040](https://github.com/microsoft/pyright/discussions/5040))
— but the price is parallel suppression comments (`# type: ignore[code]` and
`# pyright: ignore[rule]` on the same line) and satisfying multiple
non-equivalent strictness contracts. Default to one gate; adopt multi-checker
only as a deliberate, documented choice.

## Claims not to repeat as fact

- **Speed multipliers** ("3–5x", "10–100x faster") and **conformance
  percentages** for these checkers trace to a small number of blog posts with
  undisclosed methodology; several were flagged or refuted in verification.
  Say "pyright is faster than mypy; the Rust checkers are faster still" and
  stop there.
- **Named adopters** ("framework X switched to ty") trace to individual social
  posts — treat as directional buzz, not evidence.
- Corporate acquisition rumors about the toolchain vendors are unverified —
  do not repeat them.

## Sources

- mypy vs pyright vs ty comparison — [pydevtools.com/handbook/explanation/how-do-mypy-pyright-and-ty-compare/](https://pydevtools.com/handbook/explanation/how-do-mypy-pyright-and-ty-compare/)
- basedpyright's mypy comparison — [docs.basedpyright.com/dev/usage/mypy-comparison/](https://docs.basedpyright.com/dev/usage/mypy-comparison/)
- Practitioner trade-off thread — [discuss.python.org/t/mypy-vs-pyright-in-practice/75984](https://discuss.python.org/t/mypy-vs-pyright-in-practice/75984)
- ty announcement — [astral.sh/blog/ty](https://astral.sh/blog/ty)
- Pyrefly vs ty deep comparison — [blog.edward-li.com/tech/comparing-pyrefly-vs-ty/](https://blog.edward-li.com/tech/comparing-pyrefly-vs-ty/)
- Pyrefly + Pydantic — [pyrefly.org/blog/pyrefly-pydantic](https://pyrefly.org/blog/pyrefly-pydantic)
