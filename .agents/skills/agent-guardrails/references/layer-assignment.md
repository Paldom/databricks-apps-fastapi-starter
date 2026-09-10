# Which check runs at which layer

Contents: [The table](#the-table) · [Decision rules](#decision-rules) ·
[Duplication policy](#duplication-policy) · [Rollout](#rollout) ·
[The dissent](#the-dissent) · [Sources](#sources)

The three enforcement layers around an agent-edited Python repo: agent-edit
(Claude Code hooks) → commit (pre-commit) → merge (CI + rulesets). This
assignment is strong practitioner consensus, not an official specification —
present it as convention. The governing principle: cheap, deterministic,
single-file checks live close to the edit; anything needing the whole repo or
a clean environment goes to CI; only CI is un-bypassable.

## The table

| Check | Agent hook | pre-commit | CI |
| --- | --- | --- | --- |
| Format (`ruff format`) | ✅ PostToolUse, single file, `--check` (report; auto-fix here trips the agent's stale-file check) | ✅ auto-fix | `--check` only |
| Lint (`ruff check`) | ✅ single file, report | ✅ staged files, `--fix` | ✅ full repo, no fixes |
| Secret scan | ✅ quick regex pass | ✅ canonical home | ✅ mandatory backstop (catches `--no-verify`) |
| Type check | ⚠️ only if sub-second on one file | ⚠️ often too slow; mirrors-mypy env pitfalls | ✅ authoritative full run |
| Tests | ⚠️ Stop hook, narrow fast subset | ⚠️ pre-push stage at most | ✅ full suite + coverage gate |
| Dangerous commands (`--no-verify`, force-push, bare pip) | ✅ PreToolUse deny — unique to this layer | — | ruleset blocks force-push server-side |
| Protected paths (`.env`, lockfiles, `.github/`) | ✅ PreToolUse deny, pre-write | — | CODEOWNERS + rulesets |
| Whole-diff / cross-file checks | ❌ hooks see one action | ✅ | ✅ |
| License, dependency, integration scans | ❌ too slow | ❌ | ✅ only sensible home |
| Mergeability | ❌ | ❌ | ✅ branch protection only |

## Decision rules

- "Never do X" invariants (destructive commands, forbidden paths) →
  PreToolUse hard deny. This is the one capability no later layer has:
  refusing the write **before the file exists on disk**.
- Deterministic single-file checks → PostToolUse soft feedback, re-verified
  at pre-commit. Sub-second budget; the hook runs on every matching call.
- Turn-level verification ("don't say done with red checks") → Stop hook.
  When the repo has pre-commit, the Stop hook runs *that config* over the
  change set (`pre-commit run --files`) — delegation, not duplication: the
  same gate, evaluated before sign-off instead of at commit. Otherwise one
  fast verify command. CI stays the real gate.
- Whole-diff, contributor-agnostic checks → pre-commit.
- Slow, environment-dependent, or security-critical → CI (security-critical
  runs at pre-commit AND CI).
- Anything about who may merge → branch protection/rulesets only.

## Duplication policy

Never duplicate an expensive check across layers unless one layer fixes and the
others only verify (`ruff format` at pre-commit, `ruff format --check` at the
hook and in CI). Running the identical blocking check three
times is the "running ruff three times" complaint — the layers exist to catch
*different* failure classes, not to repeat each other. If CI has to fix
something, the earlier layers didn't do their job; if a hook takes 30 seconds,
it's at the wrong layer. Delegation is the exception that proves the rule: a
Stop gate running `pre-commit run --files` is not a second definition of the
checks, it is the same definition evaluated earlier — duplication means
maintaining two *definitions*, which is what drifts.

## Rollout

Observe → warn → enforce, one verb per hook:

1. Week 1: log-only — no denies; collect what would have fired.
2. Week 2: narrow PreToolUse denies for patterns that caused actual damage.
3. Ongoing: precise matchers (`Edit|Write`, never a catch-all), every
   committed hook documented in onboarding, false positives reviewed weekly.

Hooks that install packages, mutate unrelated files, or run CI-scale work on
every edit are the ones contributors disable — and a disabled guardrail is
worse than none, because it still looks installed.

## The dissent

A minority position ("pre-commit is dead when you have agents") argues
agent-scale edit frequency makes local commit-time hooks impractical and
pushes everything to CI as commodity compute. The mainstream keeps all three
layers. Where a team lands usually depends on how fast their local checks
are — which is an argument for keeping hooks single-file and sub-second, not
for deleting layers. If installed, the python-precommit and python-ci skills
own those layers' contents.

## Sources

- pre-commit — https://pre-commit.com
- Protected branches — https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- Hooks docs — https://code.claude.com/docs/en/hooks
- Layered setup example — https://github.com/trailofbits/claude-code-config
- Agent-native repo case study — https://blog.streamlit.io/the-repo-is-the-harness-how-we-made-an-8-year-old-codebase-agent-native-75629a953354
