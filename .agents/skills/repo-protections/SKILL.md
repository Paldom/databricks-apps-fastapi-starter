---
name: repo-protections
description: Configures GitHub repository protections - rulesets (require PR, required checks, no force pushes), secret scanning and push protection, Dependabot, private vulnerability reporting, and Actions hardening. Use when the user asks to protect a branch, set up branch protection or rulesets, enable security features, or harden a repo. Not for writing SECURITY.md or fixing code vulnerabilities.
license: MIT
argument-hint: [ruleset|scanning|dependabot|pvr|all]
---

# repo-protections

Applies the **server-side** gates that client-side hooks and good intentions can't
replace. The failures this skill fixes: models suggest the legacy branch-protection
UI instead of rulesets, don't know the `gh api` payloads, forget that CODEOWNERS
does nothing until a ruleset requires code-owner review, and let bot PRs auto-merge.

## When NOT to use

- `SECURITY.md` and other prose files → `community-health`.
- Fixing a vulnerability in code, rotating leaked credentials → incident work, not
  settings.
- Release pipelines / OIDC trusted publishing → out of scope here.
- CI workflow authoring → out of scope (naming required checks is in scope).

## Workflow

1. **Audit first** (read-only; degrades gracefully on 403/404):
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/check_protections.py" [owner/repo]
   ```
   Reports: ruleset/protection on the default branch, secret scanning, push
   protection, Dependabot config, PVR — with pass/warn/fail per control.
2. **Read `references/protections-playbook.md`**, then apply what's missing, in
   this order (each step has the exact command in the playbook):
   - **Ruleset on the default branch** (prefer rulesets over classic protection:
     auditable bypasses, apply to admins, org-inheritable): require PR; required
     status checks named **exactly** as they report (matrix CI → one aggregator
     job as the only required check; merge queues need the `merge_group` trigger);
     block force pushes and deletions; require code-owner review **only if**
     CODEOWNERS exists — and if it doesn't, say that CODEOWNERS + this toggle is
     the pair that makes path ownership real.
   - **Secret scanning + push protection** — default on public; private repos need
     GHAS/Secret Protection. Enable via the `security_and_analysis` PATCH.
   - **Dependabot** — `.github/dependabot.yml` for the ecosystems actually in the
     repo: weekly, grouped, 7-day cooldown. State the two limits: security updates
     bypass cooldown by design; cooldown does not cover transitive npm deps. Never
     recommend blanket auto-merge of bot PRs — bots carry unearned trust; they get
     the same CI + review gate as humans.
   - **Private Vulnerability Reporting** — public repos only, off by default.
   - **Actions hardening** (baseline only): pin third-party actions to commit SHAs
     with a version comment, top-level `permissions: contents: read`, per-job
     elevation, caution with `pull_request_target`.
3. **Verify**: re-run the check script; every applied control must show as active.
   For rulesets also confirm with `gh api repos/{owner}/{repo}/rulesets`.
4. **Report** what was enabled, what was skipped and why (plan limits, missing
   CODEOWNERS, private-repo constraints).

## Output spec

Requested protections active and verified by re-audit; anything unapplicable
(private repo on free plan, missing GHAS) reported explicitly with the unlock
condition — never silently skipped.

## Gotchas

- Rulesets and branch protection on **private** repos require a paid plan; the API
  returns 403/upgrade errors — surface that, don't retry blindly.
- A required status check that has never run on the repo can't be selected/matched;
  run the workflow once first.
- Required checks match on the reported check name, not the workflow filename.
- Secret-scanning push protection blocks only known patterns — present it as one
  layer, not a guarantee.
- Enabling everything on a fork or throwaway is noise — confirm the repo is the
  long-lived one before applying org-grade gates.

## Files

- `references/protections-playbook.md` — ruleset recipe with `gh api` JSON payload,
  per-control commands + verification, minimum-viable posture table, Scorecard note.
- `scripts/check_protections.py` — read-only audit; non-zero exit when the default
  branch has no ruleset/protection.
