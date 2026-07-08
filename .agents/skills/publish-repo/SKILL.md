---
name: publish-repo
description: Publishes this Agent Skills repository to skills.sh - pre-flight checks, public visibility flip, protections (PVR, ruleset), consumer-style install verification, telemetry seeding, and repo-page groupings. Use when the user asks to publish, deploy, release, go public, or get listed on skills.sh. Not for authoring skills or editing scaffold infrastructure.
disable-model-invocation: true
argument-hint: [--dry-run]
---

# publish-repo

Deploys this repository to the skills.sh ecosystem. There is no publish API —
deployment = a public, installable repo plus a first install that seeds the
catalogue telemetry. This skill makes that sequence deliberate instead of ad hoc.
Slash-invoked only: it flips repository visibility, which is hard to undo socially
(anything ever pushed becomes visible).

## When NOT to use

- Writing or fixing a skill → `add-skill`.
- The repo has zero skills under `skills/` → build first; never publish an empty
  catalogue.
- Routine pushes to an already-public repo → plain git.

## Workflow

1. **Pre-flight (hard gates — stop on any failure):** the working tree must be
   clean and pushed **by the owner** — this skill never runs `git commit` or
   `git push`; if there are uncommitted changes, stop and hand the list to the
   owner instead.
   ```bash
   git status --porcelain          # must be empty
   make check                      # must end: 0 error(s)
   npx skills add . --list        # every skill under skills/ discovered
   gh skill publish --dry-run     # spec validation (gh >= 2.90; public preview)
   python3 -c "import json; json.load(open('skills.sh.json'))"
   ```
   Triage every `gh skill` warning: add missing `license: MIT` frontmatter; the
   `.claude/skills/` warning is expected here (bundled first-party dev skills,
   committed by design — not third-party content). Also verify: README catalogue
   + CHANGELOG current; every skill description is benefit-led (it is the listing
   copy); CI green on the latest commit.
2. **Manual blockers — require explicit user confirmation, never assume:**
   - full-history secret scan (gitleaks/trufflehog) done;
   - personal/private-file review done (everything ever committed goes public).
   With `--dry-run` in `$ARGUMENTS`, stop here and report readiness instead.
3. **Groupings:** ensure `skills.sh.json` lists every skill in exactly one group
   with an engaging one-sentence description per group (see docs/deploying.md).
4. **Flip visibility** (confirm with the user immediately before):
   ```bash
   gh repo edit <owner>/<repo> --visibility public --accept-visibility-change-consequences
   ```
5. **Protections** (public repo unlocks them):
   ```bash
   gh api repos/<owner>/<repo>/private-vulnerability-reporting --method PUT
   ```
   Add a default-branch ruleset. Solo-maintainer default: block force pushes and
   deletions only (a require-PR rule would block the owner's direct-push
   workflow); when outside contributors arrive, upgrade to require-PR +
   code-owner review + the `validate` check. Also add a **tag ruleset** on `v*`
   (block update + deletion) so published releases are immutable.
6. **Release** — cut a versioned GitHub release matching `.claude-plugin/plugin.json`:
   ```bash
   gh skill publish --tag v<version>
   ```
   It re-validates, adds the `agent-skills` topic if missing, and creates the
   release with auto-generated notes. Add the `skills-sh` topic too:
   `gh repo edit <owner>/<repo> --add-topic skills-sh`.
7. **Verify like a consumer, and seed the catalogue** (run locally, NOT in CI —
   telemetry is disabled in CI and the first real install is what lists the repo):
   ```bash
   npx skills add <owner>/<repo> --list
   mkdir -p /tmp/skills-verify && cd /tmp/skills-verify
   npx skills add <owner>/<repo> --skill '*' -a claude-code -y
   npx skills list -a claude-code
   ```
8. **Polish:** the README carries the skills.sh badge
   (`[![skills.sh](https://skills.sh/b/<owner>/<repo>)](https://skills.sh/<owner>/<repo>)`
   — scaffolded by default); set the homepage (`gh repo edit --homepage`, e.g. to
   `https://skills.sh/<owner>/<repo>`); remind about the social preview image
   (manual UI step).
9. **Report:** repo URL, skills.sh page URL, install command, release tag,
   protections applied, what was skipped (with unlock conditions), and the note
   that the skills.sh page appears after telemetry processes the seed install
   (pages are cached).

## Output spec

Public repo installable via `npx skills add <owner>/<repo>` (verified by an
actual install), PVR enabled, ruleset active, skills.sh.json valid with every
skill grouped, seed install performed, user told exactly what to expect next.

## Gotchas

- Visibility flip is the point of no return for history — that is why step 2
  demands explicit confirmation and never self-certifies.
- `npx skills add . --list` failing with "No skills found" means frontmatter or
  layout problems — fix via `make check` output, never by restructuring blindly.
- The leaderboard/repo page lags the seed install; absence minutes later is
  normal, not failure.
- Do not enable a require-PR ruleset on a solo repo whose workflow pushes to
  main directly — it will block the owner; use the staged default in step 5.
