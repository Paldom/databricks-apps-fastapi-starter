---
name: repo-audit
description: Audits a GitHub repository against a professional open-source checklist - README quality, metadata, community files, intake templates, protections, activity - and returns a scored gap report with prioritized fixes. Use when the user asks to audit, health-check, or score their repo, or asks what's missing before going public. Not for fixing a single named file or code-level security audits.
license: MIT
argument-hint: [owner/repo (defaults to current repo)]
---

# repo-audit

The composite view: measures a repository against the professional-OSS bar and
says **what to fix first and which skill fixes it**. The failure this skill fixes:
ad-hoc audits that check whatever comes to mind, miss whole categories (metadata,
protections), and produce unprioritized nag-lists that ignore project stage.

## When NOT to use

- The user names the fix ("write a README", "add topics", "protect main") → route
  straight to the focused skill; don't audit first.
- Code-level bug hunting or PR security review → code-review work, not repo setup.
- CI pipeline debugging → out of scope (CI *presence* is in scope).

## Workflow

1. **Collect evidence mechanically** — no vibes:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/collect_evidence.py" [owner/repo] > /tmp/repo-evidence.json
   ```
   Gathers: repo metadata (`gh repo view --json`), community-profile health
   percentage, file presence (README/LICENSE/health files/templates/workflows),
   protections and security settings, releases, archive status, latest CI run.
   Every value is tri-state — `null` means *not determinable* (permissions, plan
   limits), and the JSON's `not_collected` list names checks that are manual or
   agent-judged by design.
2. **Score** with `references/audit-checklist.md`: six categories, each with
   weighted checks — README quality, discoverability, community health files,
   contribution intake, protections, vital signs. Compute per-category scores and
   the overall grade (A ≥90 … D). Checks answered by evidence fields score
   mechanically; checks in `not_collected` are scored by you reading the repo (say
   so in the report) or marked "manual review required" — never inferred from
   silence, and `null` evidence is always reported as unknown, not failing.
3. **Right-size before reporting.** Apply the checklist's stage rules: a solo
   hobby repo is *not graded down* for missing GOVERNANCE or elaborate templates —
   mark those "deferred by stage", not failing. Non-negotiables at every stage:
   LICENSE, README basics, no leaked secrets.
4. **Report** (template in the checklist): per-category score table, overall grade,
   then the **top-5 prioritized fixes**, each with impact, effort, and the owning
   skill (`readme-author`, `repo-discoverability`, `community-health`,
   `issue-pr-templates`, `repo-protections`).
5. **Going-public pre-flight** (when asked "before I make it public"): add the
   flip-specific blockers — license present (evidence-backed), PVR to enable right
   after the flip, social preview ready, **plus two MANUAL blockers the evidence
   never covers**: a secret scan of the full git history (gitleaks/trufflehog) and
   a personal/private-file review. List those two as unchecked boxes the maintainer
   must do — never present them as passed. Split blockers from nice-to-haves.
6. **Fix nothing unasked.** Offer to run the owning skill for the top items.

## Output spec

A report containing: evidence-backed per-category scores, an overall grade, a
top-5 fix list with owner-skill routing, stage-deferred items clearly marked, and
zero modifications to the repository.

## Gotchas

- Some evidence needs permissions: traffic stats need push access; protections and
  security flags can 403 on private/free plans — the script degrades to "unknown";
  report unknowns as unknowns, never as failures.
- The community-profile health percentage only counts public-repo files — on
  private repos rely on the file-presence checks instead.
- Don't chase 100/100: the checklist encodes diminishing returns; say when a repo
  is already past the bar its stage needs.
- One audit per repo per conversation — re-run only after fixes land.

## Files

- `references/audit-checklist.md` — the six-category weighted checklist, scoring
  rubric, stage rules, report template.
- `scripts/collect_evidence.py` — mechanical evidence collector (gh + filesystem),
  JSON to stdout; exits non-zero only when the target repo can't be read.
