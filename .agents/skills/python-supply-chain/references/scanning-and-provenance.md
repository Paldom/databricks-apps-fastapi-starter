# Scanning workflows and provenance artifacts

**Contents:** [Action pinning note](#action-pinning-note) ·
[Secret scanning and push protection](#secret-scanning-and-push-protection) ·
[gitleaks CI backstop](#gitleaks-ci-backstop) ·
[Secret-found playbook](#secret-found-playbook) ·
[CodeQL](#codeql) · [Scheduled pip-audit](#scheduled-pip-audit-workflow) ·
[OpenSSF Scorecard](#openssf-scorecard) · [SBOM generation](#sbom-generation) ·
[Release attestations](#release-attestations) ·
[Verification — the part everyone skips](#verification--the-part-everyone-skips)

## Action pinning note

Every `uses:` below is written as `owner/action@<commit-sha>  # vX.Y.Z` with a
placeholder. Before committing, resolve the full commit SHA of the current release
tag and substitute it:

```bash
gh api "repos/<owner>/<action-repo>/commits/<tag>" --jq .sha
```

Mutable tags (`@v2`) have been repointed to malicious commits in real attacks
(GhostAction, tj-actions). The repo-wide pinning policy and its audit tooling
(zizmor) belong to the python-ci skill — this note exists so the workflows *this*
skill adds don't arrive unpinned.

## Secret scanning and push protection

State of the platform: 200+ provider detectors, partner auto-revocation, validity
checks, and org-wide enforced enablement. Free and on by default for public repos;
private repos require GitHub Secret Protection licensing.

```bash
# Enable/verify both toggles (needs admin):
gh api -X PATCH "repos/{owner}/{repo}" --input - <<'EOF'
{ "security_and_analysis": {
    "secret_scanning": { "status": "enabled" },
    "secret_scanning_push_protection": { "status": "enabled" } } }
EOF

# Check current state:
gh api "repos/{owner}/{repo}" --jq .security_and_analysis
```

Push protection blocks a detected secret before the push lands — the secret never
enters history. Caveat GitHub itself documents: it blocks only a subset of
high-confidence patterns. That is why the CI backstop below stays even when push
protection is on. Background reading: GitHub's own triage playbook,
<https://github.blog/security/application-security/how-github-used-secret-scanning-to-reach-inbox-zero/>.

## gitleaks CI backstop

Catches generic/entropy patterns push protection misses and any local-hook bypass
(`git commit --no-verify`). A local gitleaks pre-commit hook is good fast feedback
but advisory — wiring it is the python-precommit skill's job; CI is the boundary.

```yaml
# .github/workflows/secret-scan.yml
name: secret-scan
on: [push, pull_request]
permissions:
  contents: read
jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<commit-sha>          # vX.Y.Z — see pinning note
        with:
          fetch-depth: 0        # full history: scan every commit in the push
      - uses: gitleaks/gitleaks-action@<commit-sha>  # vX.Y.Z
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}   # required for ORG repos
```

- **Org-repo gotcha**: gitleaks-action requires a `GITLEAKS_LICENSE` key for
  organization-owned repos (free for personal accounts). Without it the job fails —
  better than silently passing, but plan for it.
- Alternative/addition: TruffleHog verifies candidate secrets against provider APIs
  so it only reports *live* credentials — strong signal, fewer false positives:
  `trufflehog git file://. --since-commit <base> --results=verified --fail`.

## Secret-found playbook

1. **Rotate/revoke the credential immediately.** This is the fix; everything else
   is cleanup. Assume the secret is compromised the moment it was pushed.
2. Only then consider history rewriting (`git filter-repo`) — and say plainly that
  rewriting does not un-leak: clones, forks, caches, and scrapers already have it.
3. Close the alert in the Security tab with the resolution recorded.
4. Confirm push protection + the CI backstop are on so the class recurs as a block,
   not an incident.

## CodeQL

Default setup — right answer for pure-Python repos, no workflow file to maintain:

```bash
gh api -X PATCH "repos/{owner}/{repo}/code-scanning/default-setup" -f state=configured
gh api "repos/{owner}/{repo}/code-scanning/default-setup"    # verify
```

Advanced setup, only when query packs or workflow-file scanning are needed:

```yaml
# .github/workflows/codeql.yml
name: codeql
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
  schedule: [{ cron: "0 4 * * 1" }]
permissions:
  contents: read
jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
    strategy:
      matrix:
        language: [python, actions]   # 'actions' scans the workflow files themselves
    steps:
      - uses: actions/checkout@<commit-sha>                 # vX.Y.Z
      - uses: github/codeql-action/init@<commit-sha>        # vX.Y.Z
        with:
          languages: ${{ matrix.language }}
      - uses: github/codeql-action/analyze@<commit-sha>     # vX.Y.Z
```

Notes: Python needs no build step. Free for public repos; private needs GitHub Code
Security. Blocking merges on code-scanning severity is done via repository rulesets —
python-ci's territory. A November 2025 platform change makes default setup bypass
restrictive org Actions policies (unless Actions is fully disabled), so coverage
isn't silently lost — worth knowing when an org policy seems contradicted.

## Scheduled pip-audit workflow

Only add when the user wants recurring audit output in CI (Dependabot security
updates already cover alerting). Scan workflow, not a quality gate:

```yaml
# .github/workflows/dep-audit.yml
name: dep-audit
on:
  schedule: [{ cron: "0 5 * * 1" }]
  workflow_dispatch:
permissions:
  contents: read
jobs:
  pip-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<commit-sha>          # vX.Y.Z
      - uses: astral-sh/setup-uv@<commit-sha>        # vX.Y.Z
      - run: uv export --format requirements-txt --no-emit-project -o audit-req.txt
      - run: uvx --from pip-audit==2.10.1 pip-audit -r audit-req.txt --no-deps
        # ==2.7.3 is an example pin — substitute the current PyPI release
```

## OpenSSF Scorecard

```yaml
# .github/workflows/scorecard.yml
name: scorecard
on:
  schedule: [{ cron: "30 2 * * 1" }]
  push: { branches: [main] }
permissions: read-all
jobs:
  analysis:
    runs-on: ubuntu-latest
    permissions:
      security-events: write   # SARIF upload
      id-token: write          # publish_results signing
    steps:
      - uses: actions/checkout@<commit-sha>            # vX.Y.Z
        with:
          persist-credentials: false
      - uses: ossf/scorecard-action@<commit-sha>       # vX.Y.Z
        with:
          results_file: results.sarif
          results_format: sarif
          publish_results: true       # feeds the public scorecard.dev API/badge
      - uses: github/codeql-action/upload-sarif@<commit-sha>   # vX.Y.Z
        with:
          sarif_file: results.sarif
```

How to frame it for the user: a 0–10 heuristic posture dashboard
(<https://github.com/ossf/scorecard/blob/main/docs/checks.md>), useful for spotting
which controls are off and for downstream consumers evaluating the project. Not a
gate: maintainers call the checks heuristic; scores are gameable (SHA-pinning purely
for points); and the public weekly scan omits CI-Tests, Contributors, and
Dependency-Update-Tool checks for API-cost reasons, so it reads lower than a local
run. A large academic sample of research repos averaged 3.5/10 — low scores are the
norm, not an emergency.

## SBOM generation

| Path | Produces | Use when |
|---|---|---|
| `gh api "repos/{owner}/{repo}/dependency-graph/sbom" --jq .sbom` | SPDX JSON of the repo's dependency graph | compliance asks "send us an SBOM" |
| `cyclonedx-py` from the exported lockfile | CycloneDX of the *built artifact's* deps | shipping an SBOM next to the wheel |
| `syft` | either format, broader ecosystem coverage | container images / mixed repos |

```bash
uv export --format requirements-txt --no-emit-project -o /tmp/sbom-req.txt
uvx --from cyclonedx-bom==7.3.1 cyclonedx-py requirements /tmp/sbom-req.txt -o sbom.cdx.json
# ==4.4.3 is an example pin — substitute the current PyPI release
```

An SBOM is inventory, not assurance: it says what's inside, not whether the build
that produced it was compromised, and it only becomes actionable when cross-checked
against a live vulnerability feed (OSV/NVD — pip-audit and osv-scanner do exactly
that). Regulatory drivers making SBOMs table stakes for commercial consumers: US EO
14028 and the EU Cyber Resilience Act.

## Release attestations

Inside the release workflow (the workflow itself — tag trigger, build, PyPI publish
via trusted publishing — is the python-release skill's territory):

```yaml
permissions:
  contents: read
  id-token: write          # OIDC identity for signing
  attestations: write
steps:
  # ... build step producing dist/ ...
  - uses: actions/attest-build-provenance@<commit-sha>   # vX.Y.Z
    with:
      subject-path: "dist/*"
  - uses: actions/attest-sbom@<commit-sha>               # vX.Y.Z
    with:
      subject-path: "dist/*"
      sbom-path: "sbom.cdx.json"
```

GitHub Artifact Attestations are built on Sigstore; the workflow's OIDC identity is
the ephemeral signing key (docs:
<https://docs.github.com/en/actions/concepts/security/artifact-attestations>).
Known limits to state up front: provenance from private repos is restricted
(enterprise-gated — check current docs), trusted-publishing/attestation flows don't
cover self-hosted runners or non-GitHub CI, and OIDC reduces but does not eliminate
token risk — a compromised workflow run can still mint valid short-lived credentials.

## Verification — the part everyone skips

An attestation proves *where and how* an artifact was built, not that it is safe:
real campaigns have produced cryptographically valid SLSA Build L3 attestations for
malicious packages by compromising the pipeline itself ("The signature is real. The
software is not." —
<https://medium.com/governed-at-the-source/the-signature-is-real-the-software-is-not-4489b1c639f8>).
Two consequences:

1. Consumers must actually verify:
   `gh attestation verify dist/pkg-1.0.0-py3-none-any.whl --repo OWNER/REPO`
   — put this line in the release notes / README so the artifact's verifiability is
   discoverable.
2. The controls that protect the *pipeline* (workflow permissions, pinning, rulesets
   — python-ci) are what give the attestation meaning. Provenance without pipeline
   hardening is a signed receipt from a burgled shop.
