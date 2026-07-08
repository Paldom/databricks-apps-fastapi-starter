# Repository Protections Playbook

Server-side protections and automated dependency/secret hygiene for a GitHub repo.
Every control states what it protects against, the exact command to enable it
non-interactively, and how to verify it stuck. Run commands with `gh` authenticated
as a repo admin; replace `OWNER/REPO` throughout.

## Contents

- [Rulesets vs classic branch protection](#rulesets-vs-classic-branch-protection)
- [The standard main ruleset](#the-standard-main-ruleset)
  - [Create it non-interactively](#create-it-non-interactively)
  - [Naming required status checks correctly](#naming-required-status-checks-correctly)
  - [Wire up CODEOWNERS](#wire-up-codeowners)
  - [Verify the ruleset](#verify-the-ruleset)
- [Secret scanning and push protection](#secret-scanning-and-push-protection)
- [Dependabot hygiene](#dependabot-hygiene)
- [Private vulnerability reporting](#private-vulnerability-reporting)
- [Actions hardening baseline](#actions-hardening-baseline)
- [Minimum-viable posture](#minimum-viable-posture)
- [Auditing posture with OpenSSF Scorecard](#auditing-posture-with-openssf-scorecard)
- [Final verification checklist](#final-verification-checklist)

---

## Rulesets vs classic branch protection

**Prefer repository rulesets over classic branch protection.** Both enforce
reviews, checks, and push restrictions; rulesets fix classic's known gaps:

| Property | Classic branch protection | Repository rulesets |
|---|---|---|
| Applies to admins | No, unless "include administrators" is set — a frequently-flagged audit finding | Yes by default; exemptions are explicit `bypass_actors` |
| Org-wide inheritance | No — per-repo only, drifts | Yes — org rulesets target many repos at once |
| Bypass auditability | Weak | Bypass actors are declared in config; bypass events are logged and reviewable in ruleset insights |
| Layering | One rule per branch pattern | Multiple rulesets aggregate; the most restrictive rule wins |
| Dry run | No | `enforcement: "evaluate"` mode previews impact before enforcing (plan-dependent) |

If a repo has classic rules, recreate them as a ruleset, confirm it is `active`,
then delete the classic rule — do not run both long-term.

## The standard main ruleset

**Protects against:** unreviewed or direct changes landing on the default branch,
history rewrites (force push), and branch deletion. The recipe, as one ruleset on
the default branch:

1. **Require a pull request** with at least 1 approving review; dismiss stale
   approvals when new commits are pushed.
2. **Require review from Code Owners** — a CODEOWNERS file is inert without this
   flag; adding the file alone enforces nothing.
3. **Require status checks to pass**, naming each check exactly (see below).
4. **Block force pushes** (`non_fast_forward`) and **block deletion** (`deletion`).
5. **Leave `bypass_actors` empty** so the rules apply to admins too. Add a bypass
   actor only deliberately, knowing every bypass is logged.

### Create it non-interactively

```bash
gh api repos/OWNER/REPO/rulesets --method POST --input - <<'JSON'
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": true,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "tests-passed" },
          { "context": "lint" }
        ]
      }
    }
  ],
  "bypass_actors": []
}
JSON
```

Notes on the payload:

- `~DEFAULT_BRANCH` tracks the default branch even if it is later renamed.
- `strict_required_status_checks_policy: true` = "require branches to be up to
  date before merging". Fine for small repos; at high PR volume use a merge queue
  instead of forcing serial rebases.
- For a dry run, POST with `"enforcement": "evaluate"`, then PUT `"active"`.
- `require_code_owner_review: true` assumes a CODEOWNERS file exists (see below).
  If the repo has none yet, set it to `false` — flip it to `true` in the same
  change that adds CODEOWNERS, or the toggle gates nothing and misleads readers
  of the settings.
- Solo-maintainer repos: a review count of 1 blocks your own merges — either add
  yourself as a bypass actor (bypasses are logged) or set it to 0 and keep the PR
  requirement, which still blocks direct pushes.

### Naming required status checks correctly

The `context` string must match the check name GitHub reports **exactly** — for
Actions that is the job's `name:` (or the job id if unnamed). Three recurring traps:

- **Checks must have run at least once** on the repo before the settings UI can
  offer them. The API accepts any context string directly, which is why the
  non-interactive path above avoids the chicken-and-egg; a typo silently produces a
  check that never reports and blocks every merge.
- **Matrix jobs need a single aggregator check.** Each matrix combination reports
  its own check name; requiring individual legs is brittle (skipped combinations
  block merges, renames break the rule). Add a trailing job and require only it:

  ```yaml
  tests-passed:
    name: tests-passed
    needs: test          # the matrix job
    if: always()
    runs-on: ubuntu-latest
    steps:
      - run: |
          if [ "${{ needs.test.result }}" != "success" ]; then exit 1; fi
  ```

- **Merge queues need `merge_group` as a workflow trigger.** A workflow that only
  listens on `pull_request` never reports during merge-queue validation, and the
  queue silently fails. If you enable a merge queue, every workflow backing a
  required check must declare both:

  ```yaml
  on:
    pull_request:
    merge_group:
  ```

Also avoid duplicate job names across workflows — they create ambiguous check
results that can block merges unpredictably. GitHub's "Troubleshooting required
status checks" doc page covers all three traps.

### Wire up CODEOWNERS

**Protects against:** unreviewed changes to the paths that define your CI and
protections themselves — whoever can edit `.github/workflows/` can disable every
other control. Create `.github/CODEOWNERS`:

```
*             @OWNER/maintainers
/.github/     @OWNER/maintainers
```

At minimum cover `/.github/` (workflows, `dependabot.yml`, CODEOWNERS itself).
This file only gates merges because the ruleset sets
`require_code_owner_review: true`.

### Verify the ruleset

```bash
gh ruleset list --repo OWNER/REPO                 # ruleset exists, status: active
gh ruleset check main --repo OWNER/REPO           # effective rules on the branch
gh api repos/OWNER/REPO/rules/branches/main       # raw aggregated rules (API view)
```

Then prove it behaves: a direct push to `main` must be rejected, and a PR without
the required checks must show a blocked merge button.

## Secret scanning and push protection

**Protects against:** credentials entering git history, where they are effectively
public forever (history rewrites are painful; forks and caches persist). Both
features are **enabled by default on public repos** at no cost; private repos
require GitHub Secret Protection (paid add-on).

```bash
gh api repos/OWNER/REPO --method PATCH \
  -f 'security_and_analysis[secret_scanning][status]=enabled' \
  -f 'security_and_analysis[secret_scanning_push_protection][status]=enabled'
```

Verify:

```bash
gh api repos/OWNER/REPO --jq '.security_and_analysis'
gh api repos/OWNER/REPO/secret-scanning/alerts    # list open alerts (triage these)
```

Know the limits: push protection blocks only a subset of the most identifiable
secret patterns — GitHub documents it as a prevention **layer, not a guarantee**.
Treat any alert as live: rotate the credential first, then clean up. For depth, add
a secrets scanner (e.g. gitleaks) as a required CI check; local pre-commit hooks
are advisory (`--no-verify` bypasses them) — server-side push protection and the CI
check are the real boundaries.

## Dependabot hygiene

**Protects against:** shipping dependencies with known CVEs, and (via cooldown)
adopting a freshly published malicious release before the ecosystem catches it.

Enable alerts and automated security-fix PRs:

```bash
gh api repos/OWNER/REPO/vulnerability-alerts --method PUT       # Dependabot alerts
gh api repos/OWNER/REPO/automated-security-fixes --method PUT   # security-update PRs
```

Add `.github/dependabot.yml` for weekly, grouped version updates with a cooldown:

```yaml
version: 2
updates:
  - package-ecosystem: "npm"          # match your ecosystem(s)
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    groups:
      minor-and-patch:
        update-types: ["minor", "patch"]
    cooldown:
      default-days: 7
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      actions:
        patterns: ["*"]
    cooldown:
      default-days: 7
```

Know exactly what the cooldown does and does not do:

- Delays **version-update** PRs for 7 days after a release, giving the community
  time to spot a poisoned release.
- **Bypassed for security updates by design** — an advisory-driven fix PR opens
  immediately. That is the behavior you want; do not "fix" it.
- Does **not** apply to transitive npm dependencies — a direct-dependency bump can
  still pull in a day-old transitive version. Cooldown is a mitigation, not a
  supply-chain guarantee.
- Dependabot does **not alert** on GitHub Actions pinned to commit SHAs (alerts
  fire on semver-tag pins only) — a known trade-off of SHA pinning; version updates
  with a version comment still work (see Actions hardening below).

**Never blanket auto-merge bot PRs.** Real supply-chain incidents have propagated
through bot-opened dependency-update PRs merged on green CI with no human review —
bot authorship carries unearned trust, so give bot PRs the same CI + review gate
as any other PR (auto-merge at most narrow patch-level groups you explicitly chose).

Verify:

```bash
gh api repos/OWNER/REPO/vulnerability-alerts        # HTTP 204 = enabled
gh api repos/OWNER/REPO/automated-security-fixes --jq '.enabled'
gh api repos/OWNER/REPO/dependabot/alerts --jq 'length'   # alert triage backlog
```

Config errors and update-job logs appear under Insights → Dependency graph →
Dependabot in the repo UI.

## Private vulnerability reporting

**Protects against:** researchers having no private channel, so vulnerabilities get
disclosed in public issues instead.

Off by default on public repos. Enable it (UI path: Settings → Advanced Security →
Private vulnerability reporting):

```bash
gh api repos/OWNER/REPO/private-vulnerability-reporting --method PUT
```

Verify:

```bash
gh api repos/OWNER/REPO/private-vulnerability-reporting --jq '.enabled'   # true
```

## Actions hardening baseline

**Protects against:** a compromised third-party action or hijacked workflow
exfiltrating secrets or pushing code with the workflow's token.

- **Pin third-party actions to full commit SHAs**, with a version comment so humans
  and Dependabot version updates can track them:

  ```yaml
  - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8  # v4.2.2
  ```

  Mutable tags (`@v4`) have been hijacked in real attacks to exfiltrate secrets
  from every downstream repo.
- **Minimal token permissions:** set at the top of every workflow

  ```yaml
  permissions:
    contents: read
  ```

  and elevate per-job only where needed (e.g. `pull-requests: write` on one job).
- **Treat `pull_request_target` as dangerous:** it runs with secrets and a write
  token in the base-repo context. Never check out and execute untrusted PR code
  under it. Keep "Require approval for all external contributors" on for fork PRs.
- **Lint workflows in CI:** run `actionlint` (syntax/correctness) and `zizmor`
  (Actions security anti-patterns) as required checks.

Verify: `gh api repos/OWNER/REPO/actions/permissions` shows the Actions policy;
grep workflows for `uses:.*@v` (tag pins) and for missing `permissions:` blocks.

## Minimum-viable posture

These five controls together cover the majority of real-world repo-level supply
chain attacks. Everything else in this playbook is defense in depth.

| # | Control | Primary threat stopped | One-line enable |
|---|---|---|---|
| 1 | Ruleset on `main` (PR + review + checks, no force-push/delete) | Unreviewed or direct changes to the default branch | `gh api repos/OWNER/REPO/rulesets --method POST --input ruleset.json` |
| 2 | CODEOWNERS covering `/.github/` + code-owner review required | Tampering with CI/workflow definitions | commit `.github/CODEOWNERS`; flag set in ruleset |
| 3 | Secret scanning + push protection | Credential leakage into git history | `gh api repos/OWNER/REPO --method PATCH -f 'security_and_analysis[...]'` |
| 4 | Dependabot alerts + security updates + weekly grouped updates with cooldown | Known-CVE and freshly-poisoned dependencies | `PUT vulnerability-alerts` + `dependabot.yml` |
| 5 | Code scanning (CodeQL default setup) on PRs | Vulnerable code patterns merging unnoticed | `gh api repos/OWNER/REPO/code-scanning/default-setup --method PATCH -f state=configured` |

Verify #5 with `gh api repos/OWNER/REPO/code-scanning/default-setup --jq '.state'`.

## Auditing posture with OpenSSF Scorecard

Use OpenSSF Scorecard (`scorecard --repo=github.com/OWNER/REPO`, or the
`ossf/scorecard-action` workflow) as a **triage signal, not a verdict**. Its checks
(branch protection, code review, dependency-update tooling, token permissions,
pinned dependencies) are explicitly heuristic, with known false positives and
negatives, and scores can be gamed — e.g. SHA-pinning purely for points without
auditing the pinned code. Treat a low score as a prompt to run the checklist below,
a high score as necessary-but-not-sufficient, and never the number as proof.

## Final verification checklist

Run after configuring a repo; every line should pass.

- [ ] `gh ruleset list --repo OWNER/REPO` shows the main ruleset, `active`
- [ ] `gh ruleset check main --repo OWNER/REPO` lists PR review, code-owner review, required checks, no force-push, no deletion
- [ ] Required-check context names match real job names; matrix jobs sit behind one aggregator job
- [ ] If a merge queue is on: every required-check workflow triggers on `merge_group`
- [ ] `.github/CODEOWNERS` exists and covers `/.github/`
- [ ] `gh api repos/OWNER/REPO --jq '.security_and_analysis'` shows secret scanning and push protection `enabled`
- [ ] `gh api repos/OWNER/REPO/vulnerability-alerts` returns 204; `automated-security-fixes` reports `enabled: true`
- [ ] `.github/dependabot.yml` present: weekly, grouped, `cooldown.default-days: 7`, covers `github-actions` ecosystem too
- [ ] No workflow or repo setting auto-merges bot PRs unconditionally
- [ ] `gh api repos/OWNER/REPO/private-vulnerability-reporting --jq '.enabled'` is `true` (public repos)
- [ ] Workflows: SHA-pinned third-party actions, top-level `permissions: contents: read`, no unsafe `pull_request_target` checkout
- [ ] A direct push to `main` is rejected when you test it
