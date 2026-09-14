# Dependabot for Python repos — config, cooldown, and the trust model

**Contents:** [Full config](#full-annotated-config) ·
[Ecosystem choice](#ecosystem-choice-uv-vs-pip) ·
[Cooldown semantics](#cooldown-semantics) ·
[Cooldown bugs](#known-cooldown-bugs) ·
[Grouping and noise tuning](#grouping-and-noise-tuning) ·
[Auto-merge policy](#why-not-auto-merge-bot-prs) ·
[Renovate comparison](#renovate-as-the-alternative) ·
[Interplay with uv exclude-newer](#interplay-with-uv-exclude-newer) ·
[SHA-pinned action alert gap](#the-sha-pinned-action-alert-gap) ·
[Free-tier facts](#free-tier-facts)

## Full annotated config

```yaml
# .github/dependabot.yml
version: 2
updates:
  # --- Python dependencies ---
  - package-ecosystem: "uv"          # for projects managed by uv.lock
    directory: "/"                   # where pyproject.toml lives
    schedule:
      interval: "weekly"
      day: "monday"
      time: "06:00"
      timezone: "Etc/UTC"
    open-pull-requests-limit: 10     # default is 5; raise, don't disable
    cooldown:
      default-days: 7                # skip versions published in the last 7 days
      semver-major-days: 14          # be slower on majors
      semver-minor-days: 7
      semver-patch-days: 3
    groups:
      python-minor-patch:
        update-types: ["minor", "patch"]
        # majors intentionally ungrouped: breaking changes get their own PR
    labels: ["dependencies"]

  # --- GitHub Actions used by the repo's workflows ---
  - package-ecosystem: "github-actions"
    directory: "/"                   # reads .github/workflows/
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
    groups:
      actions:
        patterns: ["*"]
```

Commit the file; Dependabot picks it up on the next scheduled run (or trigger a run
from Insights → Dependency graph → Dependabot). Version *updates* (this file) are
distinct from Dependabot *alerts* and *security updates*, which are repo settings:

```bash
gh api -X PUT "repos/{owner}/{repo}/vulnerability-alerts"        # enable alerts
gh api -X PUT "repos/{owner}/{repo}/automated-security-fixes"    # enable security PRs
```

## Ecosystem choice: uv vs pip

- `package-ecosystem: "uv"` — projects with a `uv.lock`. Dependabot updates the
  lockfile and `pyproject.toml` constraints together.
- `package-ecosystem: "pip"` — `requirements*.txt`, pip-tools output, Pipenv, and
  Poetry projects (the `pip` value covers all of these).
- The uv ecosystem supports `cooldown` (`default-days` and the `semver-*-days`
  variants) like pip; the public bug history below is mostly from other
  ecosystems. After enabling, verify on the next scheduled run that PRs actually
  appear for a known-stale dependency before trusting it.

## Cooldown semantics

`cooldown` delays adoption of a freshly published version — the window in which
malicious releases (account takeovers, typosquats promoted by download counts) are
usually detected and yanked. Options per update entry:

- `default-days` — applies to everything not matched by a more specific option.
- `semver-major-days` / `semver-minor-days` / `semver-patch-days` — severity-aware
  delays (only meaningful for ecosystems where semver intent is knowable).
- `include` / `exclude` — lists of dependency name patterns to scope the cooldown.

Since 2026-07-14 github.com applies a **3-day default cooldown** to version updates
even with no `cooldown:` block (security updates still open immediately; GHES adoption
is version-dependent) — so an explicit `default-days` sets a longer or scoped window,
it does not create the control from nothing
(<https://github.blog/changelog/2026-07-14-dependabot-version-updates-introduce-default-package-cooldown/>).

The property that makes Dependabot's cooldown the right layer for this control:
**security-advisory-driven updates bypass the cooldown automatically.** A freshness
window enforced in the package manager (see `exclude-newer` below) cannot make that
distinction and will delay security fixes by the same number of days.

Announcement: <https://github.blog/changelog/2025-07-01-dependabot-supports-configuration-of-a-minimum-package-age/>

## Known cooldown bugs

- **Latest-release-only evaluation** — the filter has been observed to evaluate only
  the newest release: if that one is inside the cooldown window, Dependabot proposes
  nothing at all, instead of falling back to an older release that satisfies the
  window. Frequently-released dependencies can be wedged for months.
  [dependabot-core #14234](https://github.com/dependabot/dependabot-core/issues/14234),
  [#14579](https://github.com/dependabot/dependabot-core/issues/14579) (#14579 was
  closed with a fix for github-actions; verify current behavior for your ecosystem).
  Detection: a dependency that stays stale across several green Dependabot runs.
- **No transitive coverage (confirmed for npm)** — cooldown does not apply to
  transitive npm dependencies at all
  ([dependabot-core #14683](https://github.com/dependabot/dependabot-core/issues/14683),
  maintainer-confirmed). Whether the pip/uv updaters share the gap is unverified —
  assume cooldown covers direct dependencies only, and rely on lockfile auditing
  (pip-audit/osv-scanner) for transitives.

## Grouping and noise tuning

Alert fatigue is the top practitioner complaint about Dependabot ("PR tsunamis").
The levers, in order of impact:

1. **Groups**: one PR per group per run. Group `minor` + `patch`; leave majors
   individual. Grouping by `patterns` (name globs) also works for families like
   `pytest*`.
2. **Cooldown**: fewer, older, safer versions per run.
3. **Schedule**: `weekly` beats `daily` for humans; `monthly` risks large diffs.
4. **`open-pull-requests-limit`**: caps concurrent PRs (default 5). Setting `0`
   disables version updates entirely — don't; use security-only mode deliberately
   instead by removing the entry and keeping alerts + security updates on.
5. **Metrics view**: for alert triage, GitHub's security-alert metrics rank by
   CVSS/EPSS/patch availability — point users there rather than muting alerts.
   Dependabot treats every alert as equally urgent regardless of reachability (a
   known critique), so triage is human work.

## Why not auto-merge bot PRs

Evidence from the April 2026 malicious-`axios` incident
(<https://blog.gitguardian.com/renovate-dependabot-the-new-malware-delivery-system/>):
bots opened 154 of 214 update PRs spreading the malicious version; ~60% of
bot-opened PRs merged without human review; 50 were fully auto-merged. Auto-merge on
green CI shipped malware *faster* than manual review would have. Separately,
attackers have crafted PRs that mimic Dependabot's branding to exploit the implicit
trust in bot PRs (<https://www.darknet.org.uk/2025/06/weaponizing-dependabot-exploiting-github-automation-for-supply-chain-attacks/>).

Policy to recommend: bot PRs get CI + human review like any PR. If the user insists
on auto-merge, confine it to grouped patch updates of dev-only dependencies, with
cooldown enabled — and record that this was their call, with the incident above as
the counter-argument.

## Renovate as the alternative

| Dimension | Dependabot | Renovate |
|---|---|---|
| Hosting | native to GitHub, zero install | GitHub App (Mend-hosted) or self-hosted |
| Freshness delay | `cooldown` (advisories bypass it) | `minimumReleaseAge` |
| Config | one YAML, limited surface | JSON5 config-as-code, presets, `packageRules` |
| Grouping | `groups` | richer (monorepo presets, scheduling per rule) |
| Lockfile-only refresh | no | `lockFileMaintenance` |

Pick Renovate when the user needs per-package policies or already runs it elsewhere;
otherwise Dependabot's native integration wins on setup cost. Never run both.

**Renovate footgun**: the `pinDigest` update type can silently roll a pinned commit
SHA forward to a new commit while keeping the same version tag — quietly defeating
SHA-pinning unless disabled via `packageRules`. If the repo pins actions by SHA
(python-ci's policy), audit the Renovate config for this before enabling.

## Interplay with uv exclude-newer

`[tool.uv] exclude-newer` (settled form: an RFC 3339 timestamp; recent uv releases
also accept relative windows like `"7 days"` — verify with `uv lock`) makes the
*resolver* ignore anything published after the cutoff. It guards every `uv lock` /
`uv sync --upgrade` run, including ones a coding agent triggers on a laptop — which
Dependabot's cooldown cannot see. Run both:

- `exclude-newer` → freshness floor for all local/CI resolution; delays security
  fixes too, so keep the window short (3–7 days) or bump the timestamp routinely.
- Dependabot cooldown → freshness floor for bot PRs; advisories bypass it.

Docs: <https://docs.astral.sh/uv/reference/settings/#exclude-newer>

## The SHA-pinned action alert gap

Dependabot *alerts* fire only for actions pinned by semver tag, not by commit SHA
(documented gap: GitHub community discussions #154189 and #125481) — so the more
secure pinning pattern loses vulnerability visibility, with no free first-party fix.
Mitigation: keep the `github-actions` ecosystem entry in `dependabot.yml` — version
*updates* still propose bumps for SHA-pinned actions (with the tag comment updated) —
and treat pinning policy/auditing as python-ci territory.

## Free-tier facts

Dependency graph, Dependabot alerts, and Dependabot security updates are free for
all repos, public and private. (Secret scanning and CodeQL are free for public repos
only — see the scanning reference.)
