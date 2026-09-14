---
name: python-supply-chain
description: Hardens a Python repository's supply chain — Dependabot update automation, pip-audit vulnerability scanning, secret scanning and push protection, CodeQL, OpenSSF Scorecard, SBOMs, CODEOWNERS. Use for 'set up dependabot', 'audit dependencies', 'someone committed a key — stop that happening again', 'protect paths with CODEOWNERS', 'harden this repo'. Not for CI quality gates, workflow hardening, or PyPI publishing.
license: MIT
---

# python-supply-chain

Installs layered supply-chain controls into a Python package repository on GitHub:
dependency-update automation with a freshness delay, vulnerability and secret
scanning, code scanning, ownership rules for the paths that define automation, and
SBOM/provenance artifacts. The design premise, taken from the 2025–2026 incident wave
(the Shai-Hulud npm worm, the malicious `axios` release spread by dependency bots,
mutable-tag action compromises), is that the attack surface is now *your automation
and the first hours after a release* — so no single control below is sufficient, and
bot output is treated with the same suspicion as human PRs.

## When NOT to use

- **CI quality-gate workflows, branch rulesets, action SHA pinning, zizmor** — the
  python-ci skill, if installed, owns those. This skill only adds *scanning* and
  *update* workflows, and notes where a control depends on a ruleset.
- **PyPI trusted publishing (OIDC) and the tag-triggered publish workflow** — the
  python-release skill. This skill stops at repo-side SBOM/provenance; the publish
  step that uploads to PyPI belongs there.
- **Pre-commit hook wiring** (including a local gitleaks hook) — the
  python-precommit skill. Local hooks are advisory; this skill installs the
  enforcing server/CI layer.
- **Packaging and lockfile setup** (`uv init`, `pyproject.toml`) — python-packaging.
- **Agent hooks / AGENTS.md rules** — agent-guardrails. This skill only *protects*
  agent-config paths via CODEOWNERS.
- **Active incident response** beyond credential rotation basics — escalate to a
  human; do not attempt autonomous cleanup of a live compromise.

## Workflow

Work through the steps in order; each is independently valuable, so stop where the
user's scope ends. Steps that change GitHub settings need `gh` authenticated with
admin rights on the repo — otherwise print the commands for the user to run.

### 1. Audit the current posture

Run the bundled read-only checker from the repo root before adding anything:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_supply_chain.py" --root .           # file-level checks
python3 "${CLAUDE_SKILL_DIR}/scripts/check_supply_chain.py" --root . --github  # + GitHub-side settings via gh
```

(Invoke it from this skill's folder with an absolute path if cwd differs.) It prints
one `PASS|WARN|FAIL|NOTE check: detail` line per control and exits non-zero on FAIL.
Fix FAILs in the steps below; treat WARNs as the backlog. Never duplicate a control
that already exists — tune it instead.

### 2. Baseline: a committed lockfile

Every control below assumes the dependency set is pinned and committed: `uv.lock`
(preferred), `poetry.lock`/`pdm.lock`, or hash-pinned requirements
(`--generate-hashes` with pip-tools). If there is no lockfile, that is a
python-packaging problem — flag it and stop; auditing an unpinned dependency set
audits a guess.

### 3. Dependency-update automation (Dependabot)

Write `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "uv"        # uv.lock projects; use "pip" for requirements/pip-tools/poetry
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    cooldown:
      default-days: 7              # skip versions published < 7 days ago
    groups:
      python-minor-patch:
        update-types: ["minor", "patch"]   # majors stay individual PRs
  - package-ecosystem: "github-actions"    # keeps actions updated; pinning policy = python-ci
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 7
```

Key decisions, with detail in [references/dependabot.md](references/dependabot.md):

- **Cooldown is the supply-chain control**, not the schedule: it delays adoption of
  freshly published versions past the window in which malicious releases are usually
  caught, and it is auto-bypassed for security-advisory updates — the reason to
  prefer it over a package-manager-level freshness pin alone. Since 2026-07-14
  github.com applies a 3-day default with no config; `default-days: 7` is how you
  lengthen it deliberately (and keep it aligned with `exclude-newer`, step 5).
- **Grouping minor+patch** is the accepted fix for PR-noise complaints. Keep majors
  ungrouped so breaking changes get individual review.
- **Never blanket auto-merge bot PRs.** In the April 2026 malicious-`axios` incident
  bots opened 154 of 214 update PRs and ~60% of bot PRs merged without human review.
  Require CI plus a human review on Dependabot PRs like any other PR.
- **Renovate** is the alternative when the user needs config-as-code flexibility;
  its cooldown equivalent is `minimumReleaseAge`. Trade-offs and its `pinDigest`
  footgun are in the reference. Pick one bot — running both doubles the noise.
- Cooldown (`default-days`, and `semver-*-days` for pip/uv) is supported for the
  pip, uv, pre-commit and github-actions ecosystems; after enabling, confirm update
  PRs actually arrive on the next scheduled run.

### 4. Vulnerability audit of the lockfile (pip-audit)

Audit the *project's* pinned set, exported from the lockfile:

```bash
uv export --format requirements-txt --no-emit-project -o /tmp/audit-req.txt
uvx --from pip-audit==2.10.1 pip-audit -r /tmp/audit-req.txt --no-deps
```

(`==2.10.1` is an example pin — check PyPI for the current release and pin that.
Unpinned `uvx` executes whatever was published minutes ago: the exact attack this
skill exists to prevent.) Plain-pip fallback, run inside the project environment:
`python -m pip install pip-audit==2.10.1 && pip-audit`.

- Do NOT run bare `uvx pip-audit` with no `-r`: it audits pip-audit's own ephemeral
  environment, not your project, and reports a clean bill for the wrong thing.
- `--no-deps` skips re-resolution and is correct because the export is fully pinned.
- Report findings with the fix version per package; do not blind-upgrade everything,
  and avoid `pip-audit --fix` in automation (it mutates the environment, not the
  lockfile).
- Alternatives: `osv-scanner` (Go binary) reads `uv.lock` directly; `uv audit`
  (preview since June 2026, OSV-backed, lockfile-aware) is the zero-install option
  once it stabilizes — pin the uv version you verified it with.
- Recurrence: Dependabot security updates cover the alerting side; add a scheduled
  scan workflow only if the user wants audit output in CI (workflow shape in
  [references/scanning-and-provenance.md](references/scanning-and-provenance.md)).

### 5. Resolution freshness window (uv projects)

For uv projects, add a resolver-level buffer against just-published packages:

```toml
[tool.uv]
exclude-newer = "2026-06-27T00:00:00Z"   # resolver ignores anything published after this
```

uv also accepts a relative window — `exclude-newer = "7 days"` (or ISO 8601
`P7D`) — and `exclude-newer-package` scopes the cutoff per package; run `uv lock`
after setting it. The cutoff compares each *artifact's* upload time, not the
release date, so a wheel uploaded late is filtered on its own.
Two gotchas: a fixed timestamp freezes resolution in the past until someone bumps it
(add it to the release checklist), and unlike Dependabot's cooldown it delays
security fixes too — which is why you run *both*: `exclude-newer` guards `uv lock`
runs on laptops and CI, cooldown guards the bot, security advisories bypass the bot's
cooldown. Reference: <https://docs.astral.sh/uv/reference/settings/#exclude-newer>.

### 6. Secret scanning, push protection, and a CI backstop

GitHub-side scanning is free and on by default for public repos; private repos need
GitHub Secret Protection licensing. Enable/verify both toggles:

```bash
gh api -X PATCH "repos/{owner}/{repo}" --input - <<'EOF'
{ "security_and_analysis": {
    "secret_scanning": { "status": "enabled" },
    "secret_scanning_push_protection": { "status": "enabled" } } }
EOF
```

Push protection blocks a detected secret *before it enters history* — strictly
stronger than any after-the-fact scan — but GitHub documents that it only blocks a
subset of high-confidence patterns. Add a CI gitleaks scan as the backstop that also
catches `--no-verify` bypasses of local hooks (workflow YAML, plus the
gitleaks-action org-license gotcha, in the reference). If a secret is ever found:
**rotate the credential first**; history rewriting does not un-leak anything already
cloned, forked, or cached.

### 7. Code scanning (CodeQL)

Default setup is enough for pure-Python repos (no build step needed):

```bash
gh api -X PATCH "repos/{owner}/{repo}/code-scanning/default-setup" -f state=configured
```

Free for public repos; private repos need GitHub Code Security licensing. Use the
advanced workflow (in the reference) only when the user needs query-pack control or
`language: actions` coverage of workflow files. Making code-scanning results block
merges is a ruleset — hand that to python-ci.

### 8. CODEOWNERS for the paths that define automation

```
# .github/CODEOWNERS — LAST matching rule wins (not first)
*                      @OWNER/maintainers
/.github/              @OWNER/platform-security
/.github/CODEOWNERS    @OWNER/platform-security
/AGENTS.md             @OWNER/platform-security
/CLAUDE.md             @OWNER/platform-security
/.claude/              @OWNER/platform-security
```

Rationale: whoever can edit workflows, `dependabot.yml`, or agent instruction files
can bypass every other control, so those paths need a stricter owner than the code.
Two silent failures: CODEOWNERS enforces nothing until "require review from code
owners" is enabled in branch protection/rulesets (python-ci's territory — say so in
the handoff), and an owner without write access is ignored without error — check the
file's rendered view on GitHub for syntax/owner errors.

### 9. Posture dashboard (OpenSSF Scorecard, optional)

Add the `ossf/scorecard-action` weekly workflow (YAML in the reference) to get a
0–10 score across ~a dozen heuristics with SARIF results in the Security tab. Treat
it as a triage dashboard, not a gate: its own maintainers call the checks heuristic,
and chasing the number (e.g. pinning SHAs no one audited) is documented security
theater. Public repos can check their existing score at
<https://scorecard.dev/viewer/?uri=github.com/OWNER/REPO> before adding anything.

### 10. SBOM and release provenance

Two SBOM paths — pick per audience:

```bash
# Repo-level SPDX from GitHub's dependency graph (compliance requests):
gh api "repos/{owner}/{repo}/dependency-graph/sbom" --jq .sbom > sbom.spdx.json

# Build-time CycloneDX from the lockfile (ship next to the wheel):
uv export --format requirements-txt --no-emit-project -o /tmp/sbom-req.txt
uvx --from cyclonedx-bom==7.3.1 cyclonedx-py requirements /tmp/sbom-req.txt -o sbom.cdx.json
```

For releases, attest the built artifacts with `actions/attest-build-provenance`
(and `actions/attest-sbom` for the SBOM) inside the release workflow — snippet and
required permissions in the reference. The publish workflow itself, and PyPI-side
attestations via trusted publishing, belong to the python-release skill. Tell the
user the honest limit: an attestation proves *where and how* an artifact was built,
not that it is safe — real campaigns have shipped validly-signed malicious builds —
and it only matters if consumers verify (`gh attestation verify dist/pkg.whl
--repo OWNER/REPO`).

### 11. Re-audit and hand off

Re-run step 1; the script should report no FAILs. List remaining WARN/NOTE items
with a one-line reason each (deliberate skip vs. needs licensing vs. sibling-skill
territory).

## Output spec — what done looks like

- `.github/dependabot.yml` with a pip or uv ecosystem entry, weekly schedule,
  cooldown, grouped minor/patch updates, and a github-actions entry.
- Committed lockfile; a documented, pinned pip-audit invocation (or scheduled scan).
- Secret scanning + push protection enabled (or exact commands handed to the user
  when permissions/licensing block it), plus a CI gitleaks backstop.
- CodeQL enabled (default setup or committed workflow).
- CODEOWNERS covering `/.github/` and agent-config paths, with the
  branch-protection dependency stated in the handoff.
- Optional per scope: Scorecard workflow, SBOM artifact, attestation step wired into
  the release workflow (or delegated to python-release).
- `scripts/check_supply_chain.py --root .` exits 0.

## Failure modes and gotchas

- **`uvx pip-audit` without `-r` audits the wrong environment** (the tool's own
  ephemeral venv) and happily reports zero findings.
- **Dependabot cooldown can wedge frequently-released dependencies**: the filter has
  evaluated only the latest release, so a dep that ships weekly may never propose an
  update (dependabot-core #14234/#14579; partially fixed — verify current behavior).
  Symptom: a dependency silently months stale despite Dependabot running green.
- **Cooldown at the package-manager level blocks security fixes**; Dependabot's
  cooldown does not (advisory updates bypass it). Don't replace one with the other.
- **Cooldown is not proven for transitive dependencies** (confirmed gap for npm in
  dependabot-core #14683; unverified for pip/uv) — the lockfile audit in step 4 is
  the control that actually covers transitives.
- **Bot-authored PRs carry unearned trust**: attackers mimic Dependabot branding,
  and auto-merge-on-green shipped malware in the axios incident. Review like any PR.
- **Dependabot does not alert on SHA-pinned actions** (only semver tags) — a known
  gap between this skill's alerting and python-ci's pinning policy; the dependabot
  `github-actions` entry still proposes pin bumps, so keep it.
- **gitleaks-action requires a license key for organization repos**
  (`GITLEAKS_LICENSE` secret; free for personal accounts) — a silent-failure setup
  step people miss.
- **CODEOWNERS is last-match-wins** — a trailing `*` rule overrides every protection
  above it. Put the catch-all first, specific security paths after.
- **Push protection is a subset filter, not a guarantee** — keep the CI backstop.
- **Scorecard is gameable and heuristic** — never wire it as a merge gate; its
  public weekly scan omits several checks (CI-Tests, Contributors,
  Dependency-Update-Tool) for API-cost reasons, so scores differ from local runs.
- **Installing a Python package executes code** — at install time (build backends,
  `setup.py`) and import time. Never install a package to inspect it; read it on
  <https://inspector.pypi.io> first. Watch for typosquats (`request` vs `requests`)
  and for hallucinated package names in LLM suggestions (slopsquatting) — verify
  the exact name, repo link, and release history on pypi.org before `uv add`.
- **Free-tier boundary**: dependency graph, Dependabot alerts and security updates
  are free everywhere; secret scanning and CodeQL are free for *public* repos only —
  on private repos, hand the user the licensing decision instead of a broken toggle.

## Files

- [references/dependabot.md](references/dependabot.md) — full annotated
  dependabot.yml, cooldown semantics and bug detail, Renovate comparison,
  noise-tuning, auto-merge policy evidence.
- [references/scanning-and-provenance.md](references/scanning-and-provenance.md) —
  gitleaks/TruffleHog CI workflows, advanced CodeQL workflow, Scorecard workflow,
  SBOM/attestation snippets with permissions, verification commands.
- [scripts/check_supply_chain.py](scripts/check_supply_chain.py) — read-only posture
  audit; `--github` adds GitHub-settings checks via `gh`; exits non-zero on FAIL.
