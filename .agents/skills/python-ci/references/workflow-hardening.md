# Hardening GitHub Actions workflows

**Contents:** [Threat model](#threat-model-the-ci-runner-is-a-trust-boundary) ·
[SHA pinning](#sha-pin-every-action) ·
[GITHUB_TOKEN scoping](#minimal-github_token-permissions) ·
[zizmor and actionlint](#zizmor-and-actionlint) ·
[pull_request_target and fork PRs](#pull_request_target-and-fork-prs) ·
[Caches as a trust boundary](#caches-as-a-trust-boundary) ·
[Agent-proofing the gate](#agent-proofing-the-gate) · [Sources](#sources)

## Threat model: the CI runner is a trust boundary

2025–2026 supply-chain incidents moved the target from "the package registry" to
"the workflow that publishes to it": PyPI documented a campaign injecting code
into GitHub Actions workflows to exfiltrate publishing tokens; the tj-actions
compromise repointed a mutable action tag at malicious code for every downstream
consumer; `pull_request_target` vulnerabilities were used to compromise real
Python packages. A compromised CI run can produce validly signed, provenance-
attested artifacts — so provenance alone defends nothing. The controls that do:
minimal token permissions, SHA pinning, workflow static analysis, and respecting
the `pull_request_target`/cache trust boundaries. All four are cheap; apply all
four.

## SHA-pin every action

Tags are mutable refs. `uses: some/action@v1` executes whatever `v1` points at
*today*, on a runner that holds your token.

```yaml
# Bad — mutable, repointable
- uses: astral-sh/setup-uv@v5
# Good — immutable content address + human-readable audit comment
- uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d  # v10.0.1 (resolved 2026-09-10 — re-resolve your own)
```

Resolve tag → commit (annotated tags: pin the `^{}` dereferenced line):

```bash
git ls-remote https://github.com/astral-sh/setup-uv 'refs/tags/v10*'   # setup-uv has no floating v10 tag since 8.0.0 — full versions only
```

Rules:

- Pin **all** actions, including `actions/*` first-party ones and any reusable
  workflows referenced across repos (`uses: org/repo/.github/workflows/x.yml@SHA`).
- Always keep the `# vX.Y.Z` comment — reviewers and update tooling key off it.
- Known trade-off: Dependabot *alerts* historically fired only for tag-pinned
  actions, so SHA pinning reduces alert visibility while update PRs still work.
  Accept the trade (pinning wins) and let the python-supply-chain skill wire
  Dependabot's `github-actions` ecosystem to keep pins fresh.
- Renovate users: its `pinDigest` behavior can roll a pinned SHA forward
  automatically — make sure pin updates always arrive as reviewable PRs, never
  silent rewrites.

## Minimal GITHUB_TOKEN permissions

The workflow token defaults to whatever the repo/org default is — often broad
write. Set it in every workflow file, then widen per job:

```yaml
permissions:
  contents: read          # workflow-wide floor

jobs:
  annotate:
    permissions:
      contents: read
      pull-requests: write   # only this job comments on PRs
```

- Quality-gate jobs (lint/type/test/coverage) need `contents: read` and nothing
  else. `id-token: write` belongs only in publish jobs (python-release
  territory); `contents: write` only where something commits back — which a
  quality gate should not do (CI verifies, it does not mutate).
- Also set the repo-level Actions default to read-only
  (Settings → Actions → General → Workflow permissions), so a workflow that
  forgets a `permissions:` block fails closed instead of open.

## zizmor and actionlint

**zizmor** (https://github.com/zizmorcore/zizmor) statically analyzes workflows
for template injection (untrusted `${{ }}` interpolation into `run:`), dangerous
triggers, excessive permissions, impostor commits, and unpinned actions:

```bash
uvx zizmor==1.30.1 .github/workflows/        # pin it (>= 1.28.0: 1.27.0 printed the GitHub token under -v, GHSA-f42p-wjw5-97qh); check the repo for the current release
# no uv: python3 -m pip install zizmor==1.30.1 && zizmor .github/workflows/
```

Triage findings rather than blanket-silencing: template-injection findings in
particular are the pattern attackers actually exploit (`${{
github.event.pull_request.title }}` inside `run:` is code execution for anyone
who can open a PR — pass untrusted values through `env:` instead). Run zizmor in
CI too (a small job in ci.yml) so regressions fail the gate. Pin the version and
bump deliberately — new releases add rules that can newly fail a previously
green run.

**actionlint** catches structural errors zizmor doesn't aim at (bad needs refs,
invalid event names, shellcheck on `run:` blocks). On PyPI as `actionlint-py`;
pin the release you verify: `uvx --from actionlint-py==<version> actionlint`.
A well-formatted workflow can still be structurally invalid — formatting tools
won't catch either class.

## pull_request_target and fork PRs

`pull_request_target` runs with the **base** repo's secrets and a
read/write-capable token while being triggered by untrusted fork content. The
recurring exploit: `pull_request_target` + checkout of the PR's head ref →
attacker-controlled code runs with secrets. Real packages were compromised
through exactly this in third-party actions.

- Default to `pull_request` for everything in the quality gate. It runs the
  fork's code with a read-only token and no secrets — which is all a
  lint/type/test gate needs.
- If `pull_request_target` seems necessary (labeling, PR comments), never check
  out the PR head in that workflow, keep permissions minimal, and treat every
  `github.event.*` value as attacker input.
- Repo setting "Require approval for all external contributors" stops fork PRs
  from running workflows before a maintainer looks — cheap and effective for
  small-maintainer repos.
- GitHub has tightened `pull_request_target` and checkout defaults in rolling
  changes through 2025–2026; verify current semantics in GitHub's changelog
  rather than assuming either the old or new behavior.

## Caches as a trust boundary

Actions caches are shared within the repo's namespace. A low-trust workflow run
that can **write** a cache key which a trusted job later **restores** is a code
injection path (cache poisoning); this has featured in real postmortems when
combined with `pull_request_target`.

- Never write caches from workflows that run untrusted input with elevated
  context; never store secrets or tokens under a cached path.
- Keep cache keys content-addressed (lockfile hashes) with `restore-keys`
  prefixes; audit any workflow that combines `pull_request_target` with cache
  read/write.
- Since 2026-06-26 GitHub issues a read-only cache token when the trigger is
  untrusted (`pull_request_target`, `issue_comment`, fork `workflow_run`) and
  the cache scope is the default branch
  (https://github.blog/changelog/2026-06-26-read-only-actions-cache-for-untrusted-triggers/)
  — directionally good, but design as if fork-writable caches are hostile
  regardless of platform version.

## Agent-proofing the gate

Coding agents under pressure to "make CI green" weaken gates in recognizable
ways. Reviewer watch-list for any PR (agent or human) that touches CI:

- `|| true` or `continue-on-error: true` appended to check steps
- deleted or commented-out workflow steps/jobs; narrowed `on:` triggers or new
  path filters that skip the gate
- thresholds edited downward; check-mode flags (`--check`, `--locked`) removed
- tests rewritten to match broken behavior (green run ≠ validated change)

Structural defenses: required checks + no-admin-bypass live server-side where no
local process can edit them; the aggregator keeps the required contexts stable;
CODEOWNERS review on `.github/` (python-supply-chain skill) makes gate edits
need a second human. A gate the author of a change can rewrite is not a gate.

## Sources

- zizmor: https://github.com/zizmorcore/zizmor
- PyPI on Actions token exfiltration (the incident class driving this page):
  https://blog.pypi.org/posts/2025-09-16-github-actions-token-exfiltration/
- Cache isolation / poisoning discussion:
  https://github.com/orgs/community/discussions/194493
- Dependency caching concepts:
  https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching
- Workflow syntax (permissions blocks):
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- "GitHub Actions is the weakest link" (threat-model overview):
  https://nesbitt.io/2026/04/28/github-actions-is-the-weakest-link.html
