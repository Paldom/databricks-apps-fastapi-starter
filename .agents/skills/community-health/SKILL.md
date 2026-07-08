---
name: community-health
description: Creates or completes GitHub community health files - CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, SUPPORT, GOVERNANCE, FUNDING.yml, CODEOWNERS, LICENSE - tailored to the repo, not boilerplate. Use when the user asks for these files, contributing guidelines, a code of conduct, or to complete the community profile. Not for issue/PR templates or enabling security settings like scanning and rulesets.
license: MIT
argument-hint: [which files, or "all"]
---

# community-health

Writes the prose files GitHub surfaces around every issue, PR, and repo visit.
The failure this skill fixes: generic boilerplate that doesn't match the repo
(CONTRIBUTING files with commands that don't exist, SECURITY files pointing at
disclosure paths that 404, CODEOWNERS files that enforce nothing).

## When NOT to use

- Issue forms / PR templates / labels → `issue-pr-templates` (GitHub counts them in
  the community profile, but they're structured YAML work, not prose).
- Enabling secret scanning, rulesets, code-owner *enforcement* → `repo-protections`.
- README work → `readme-author`.

## Workflow

1. **Inspect the repo first**: language, real test/build/setup commands, maintainer
   handles, license state, project stage (solo? contributors? org?). Every file must
   reflect reality — a CONTRIBUTING that says `make test` when there is no Makefile
   is worse than no file.
2. **Right-size before writing.** Read the stage table in
   `references/health-files-guide.md`: solo/early repos need LICENSE + README + CI
   first; CODE_OF_CONDUCT/GOVERNANCE earn their keep once outside contributors
   exist. Recommend a staged order, don't dump all files unasked.
3. **Write the requested files** per the per-file requirements in the guide:
   - `CONTRIBUTING.md` — dev setup, the repo's real test/lint commands, PR workflow,
     where to propose ideas first. Surfaced by GitHub in issue/PR flows.
   - `CODE_OF_CONDUCT.md` — Contributor Covenant, unmodified; flag the contact
     placeholder for the maintainer.
   - `SECURITY.md` — private reporting path; note the PVR link 404s until enabled
     on a public repo (enforcement itself → `repo-protections`); supported versions.
   - `SUPPORT.md` — route questions away from the issue tracker.
   - `GOVERNANCE.md` — one page: roles, how decisions get made, how contributors
     become maintainers. One page beats none; skip for solo repos.
   - `FUNDING.yml` — valid platform keys only, in `.github/`.
   - `CODEOWNERS` — real handles on sensitive paths **including `.github/` and
     workflow files**; always warn it is inert until a ruleset requires code-owner
     review, and route enforcement to `repo-protections`.
   - `LICENSE` — full standard text at the root (GitHub's detector needs it);
     MIT/Apache-2.0 default; note the CLA-vs-DCO table in the guide if asked.
4. **Verify**:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/check_health_files.py" [--remote owner/repo]
   ```
   `--remote` also fetches GitHub's community-profile health percentage. Note the
   profile also counts issue/PR **templates** — if templates are the remaining gap,
   say so and route that work to `issue-pr-templates` rather than writing them here.
5. **Summarize** what was added, what was deliberately deferred and why.

## Output spec

Requested files exist, are non-empty, contain the repo's real commands/handles, and
pass `scripts/check_health_files.py`. Placeholders the maintainer must fill (CoC
contact, funding handles) are explicitly listed in the summary, not silently left.

## Gotchas

- Files are recognized in `.github/`, the root, or `docs/` — pick one convention;
  `.github/` keeps the root clean, root maximizes visibility.
- CODEOWNERS syntax errors are silent — validate paths exist and handles are real.
- Don't write a CLA unprompted; DCO is the low-friction default, and the choice
  depends on relicensing needs (see the guide's decision table).
- A `SECURITY.md` promising response times the maintainer can't keep is a liability
  — default to "best effort within 7 days" phrasing unless told otherwise.

## Files

- `references/health-files-guide.md` — per-file content requirements, stage table,
  CLA/DCO decision table, community-profile checklist.
- `scripts/check_health_files.py` — presence/content checks; `--remote` adds the
  community-profile API; non-zero exit on missing required files.
