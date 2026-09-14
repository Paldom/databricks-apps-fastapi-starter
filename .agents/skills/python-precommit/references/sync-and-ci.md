# Keeping pre-commit in sync with CI (and honest about bypass)

Version drift and silent bypass are the two ways a pre-commit setup rots. This
file covers the CI mirror, rev-update automation, SHA freezing, the bypass
model, and the alternatives/debates.

**Contents:**

1. [The double-accounting problem](#1-the-double-accounting-problem)
2. [The CI mirror job](#2-the-ci-mirror-job)
3. [pre-commit.ci and the autofix debate](#3-pre-commitci-and-the-autofix-debate)
4. [Keeping revs fresh](#4-keeping-revs-fresh)
5. [SHA freezing and the hook supply chain](#5-sha-freezing-and-the-hook-supply-chain)
6. [--no-verify, SKIP, and the honesty contract](#6---no-verify-skip-and-the-honesty-contract)
7. [prek — the Rust drop-in](#7-prek--the-rust-drop-in)
8. [Minority view — pre-commit under agents](#8-minority-view--pre-commit-under-agents)

## 1. The double-accounting problem

The same tool is typically versioned in **two or three places**:

| Place | Example |
| --- | --- |
| Hook rev | `astral-sh/ruff-pre-commit` `rev: v0.15.10` |
| Dev dependency | `ruff>=0.15.10` in `[dependency-groups] dev` / `uv.lock` |
| CI | whatever a `pip install ruff` / action installs |

When these drift, commits pass locally and fail in CI (or vice versa) — the
single most common pre-commit complaint. Fixes, in order of preference:

1. **Make CI run the identical config** (`pre-commit run --all-files`), so the
   hook rev is the only version that matters in both places.
2. **Keep the hook rev and the dev-dependency version in lockstep** — update
   them in the same PR. Tooling exists to automate the ruff case
   (e.g. `sync-with-uv`, which aligns hook revs with `uv.lock`).
3. Some teams give up on local hooks entirely (IDE format-on-save + strict CI)
   to get a single source of truth — a legitimate, slower-feedback trade.

Also pin `pre-commit` itself (dev dependency via `uv add --dev pre-commit`, and
`pip install pre-commit==X.Y.Z` in CI) — the framework's own behavior changes
across majors.

## 2. The CI mirror job

Hooks are per-clone, opt-in, and skippable; CI is the layer nobody can opt out
of. Every check in `.pre-commit-config.yaml` must re-run there. Minimal job:

```yaml
# .github/workflows/pre-commit.yml
name: pre-commit
on:
  pull_request:
  push: { branches: [main] }
jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7       # pin to full commit SHAs in production
      - uses: actions/setup-python@v7   # (tags can be re-pointed; see section 5)
        with: { python-version: "3.12" }
      - run: python -m pip install pre-commit==4.6.2   # match the version in uv.lock
      - name: cache pre-commit environments
        uses: actions/cache@v4
        with:
          path: ~/.cache/pre-commit
          key: pre-commit-${{ hashFiles('.pre-commit-config.yaml') }}
      - run: pre-commit run --all-files --show-diff-on-failure
```

Notes:

- `pre-commit run --all-files` exits 0 only when every hook passes and nothing
  was modified — clean CI pass/fail semantics. `--show-diff-on-failure` prints
  what a formatter would have changed, so the PR author can fix locally.
- `language: system` hooks (the `uv run mypy` pre-push recipe) need their tool
  installed in the job — add `uv sync` first, or scope the CI run with
  `SKIP=mypy,pytest` and let dedicated CI jobs cover those (the python-ci
  skill's territory).
- Pre-push-stage hooks don't run in `pre-commit run` by default (it runs the
  `pre-commit` stage); use `pre-commit run --all-files --hook-stage pre-push`
  in a separate step if you want them mirrored, or rely on the dedicated CI
  jobs.
- A weekly scheduled `run --all-files` catches files nobody has touched in
  recent PRs.
- [`pre-commit/action`](https://github.com/pre-commit/action) still works
  (`uses: pre-commit/action@v3.0.1`, caches hook envs) but describes itself as
  **maintenance-only** and points at pre-commit.ci — don't default to it for
  new repos without noting that.
- Anything beyond this one job — matrices, required checks, rulesets,
  aggregator jobs — belongs to the python-ci skill.

## 3. pre-commit.ci and the autofix debate

[pre-commit.ci](https://pre-commit.ci/) is the hosted service (free for OSS):
runs the hooks on every PR, can auto-commit formatting fixes, and auto-updates
revs on a schedule. Configure in-config:

```yaml
ci:
  autoupdate_schedule: weekly
  autofix_prs: true     # the contested bit — see below
  skip: [mypy, pytest]  # system-language hooks it can't run
```

The **autofix debate** is genuinely unsettled:

- Dominant community stance: **CI should enforce, not mutate** — auto-commits
  to contributor branches cause merge churn, surprise diffs, and confuse
  first-time contributors. Default to `autofix_prs: false` / plain fail.
- The autofix camp values zero-friction formatting on drive-by PRs; for
  docs-heavy OSS repos this is a defensible, deliberate choice — record it.
- Known gap: pre-commit.ci has documented failures pushing fixes to
  `.github/workflows` files (token permissions) — workflow-file hooks may
  silently go unenforced there. Keep `check-github-workflows` in your own CI
  mirror too.

## 4. Keeping revs fresh

Stale revs are the slow version of drift: the hooks keep passing while the
dev-dependency versions move on. Options:

| Mechanism | How | Notes |
| --- | --- | --- |
| Dependabot | `package-ecosystem: "pre-commit"` entry in `dependabot.yml` | Native support since 2026-03-10 (updates `rev`, honours `# frozen:` comments, groups; https://github.blog/changelog/2026-03-10-dependabot-now-supports-pre-commit-hooks/) |
| pre-commit.ci | `autoupdate_schedule: weekly` | Hosted; also runs the hooks |
| Manual cadence | `pre-commit autoupdate` monthly, in a PR | Review the diff — never blind-merge; a rev bump is a dependency bump |

Whichever mechanism: the update PR must also bump the matching dev-dependency
version (ruff, mypy) or drift reappears (section 1).

## 5. SHA freezing and the hook supply chain

Installing a hook clones an arbitrary repo and executes its code on every
commit — an attack surface flagged since 2019
([pre-commit#942](https://github.com/pre-commit/pre-commit/issues/942)).
Practical mitigations:

- **`pre-commit autoupdate --freeze`** rewrites `rev:` to full commit SHAs
  (with the tag in a comment). Tags can be silently re-pointed by a
  compromised maintainer account — a real precedent class (ua-parser-js 2021,
  eslint-scope 2018); SHAs cannot.
- Prefer hooks from well-known orgs; review rev bumps like any dependency bump.
- The same logic applies to the GitHub Actions in the mirror workflow — pin
  actions by full SHA (workflow hardening at scale is the python-ci skill's
  territory).

Trade-off: frozen SHAs are unreadable in review without the comment, and
Dependabot/pre-commit.ci handle tag pins more gracefully. Reasonable default:
tags for typical OSS, `--freeze` for security-sensitive repos.

## 6. --no-verify, SKIP, and the honesty contract

| Bypass | Effect | Caught by |
| --- | --- | --- |
| `git commit --no-verify` (`-n`) | skips ALL commit-stage hooks, silently, no log | CI mirror only |
| `git push --no-verify` | skips pre-push hooks | CI mirror only |
| `SKIP=mypy git commit …` | skips only the named hook ids | CI mirror (and it's visible in the shell history at least) |
| GitHub web-UI edits / suggested-change commits | no local hooks exist there at all | CI mirror only |
| Clone that never ran `pre-commit install` | no hooks, ever | CI mirror only |

Consequences for how to write and talk about the setup:

- Never describe a hook as "prevents X". It provides fast feedback; the CI
  mirror provides enforcement; server-side protections (push protection,
  branch rulesets) are the only true gates.
- `SKIP=<hook-id>` is the escape hatch to recommend over `--no-verify` — it
  skips one hook instead of all of them.
- **Chronic bypass is a signal, not a sin**: if people routinely skip a hook,
  it is too slow or too noisy — profile (`pre-commit run --verbose`), scope it
  (`files:`), or move it to pre-push/CI. Budgets: commit stage a few seconds,
  pre-push under ~30 s.
- Reports of coding agents reaching for `--no-verify` when stuck exist but
  rest on scattered anecdotes; the defense is the same either way (CI mirror +
  server-side rules). Configuring agent-side guardrails is the
  agent-guardrails skill's territory.

## 7. prek — the Rust drop-in

[prek](https://github.com/j178/prek) re-implements pre-commit in Rust on uv:

- Reads the same `.pre-commit-config.yaml` — migration is
  `uv add --dev prek && uv run prek install` (plus removing pre-commit).
- Community-reported wins: much faster hook installation/autoupdate, native
  monorepo support (per-subproject configs), single static binary. Speed
  claims are consistent across independent threads but community-reported —
  don't quote numbers.
- Costs: newer, less battle-tested, smaller ecosystem; pre-commit.ci doesn't
  run it (the plain CI mirror works fine since the config is identical).
- Adoption is real (used by large projects' tooling, e.g. Apache Airflow's
  steward setup, and Trail of Bits' modern-Python guidance) but pre-commit
  remains the default. Offer prek when install speed or monorepo layout is an
  actual pain point, not by default.

## 8. Minority view — pre-commit under agents

A minority position ("pre-commit is dead when you have agents", Massdriver
talk, mid-2026) argues that high-frequency agent-driven edits make local
commit-time hooks impractical — agents commit far more often than humans, hook
latency compounds, and agents bypass or fight hooks — so all checking should
consolidate into CI as commodity compute.

Status: contrarian but coherent; most published stacks (including
agent-native redesigns) still keep pre-commit as the earliest deterministic
layer, with two adaptations for agent-heavy repos:

- Keep the commit stage minimal (hygiene + format-check only) so agent commit
  loops stay fast; everything else at pre-push/CI.
- If an agent-side hook (e.g. a PostToolUse formatter) already auto-fixes on
  write, make the pre-commit hook a **check**, not a second reformat — avoids
  churn loops.

Present both positions when the user's repo is agent-heavy; deciding which
layer runs which check is the agent-guardrails skill's call.
