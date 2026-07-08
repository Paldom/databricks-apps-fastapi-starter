# Community Health Files — What to Write, Where GitHub Shows It

Guide to the prose community-health files of a repository: what each must contain,
where GitHub surfaces it, and when a project actually needs it. Issue/PR templates
and security *settings* (rulesets, scanning, PVR configuration) are covered by
sibling references — this file covers only the documents themselves.

## Contents

- [Where GitHub looks for these files](#where-github-looks-for-these-files)
- [Right-size by project stage](#right-size-by-project-stage)
- [CONTRIBUTING.md](#contributingmd)
- [CODE_OF_CONDUCT.md](#code_of_conductmd)
- [SECURITY.md](#securitymd)
- [SUPPORT.md](#supportmd)
- [GOVERNANCE.md](#governancemd)
- [FUNDING.yml](#fundingyml)
- [CODEOWNERS](#codeowners)
- [LICENSE](#license)
- [CITATION.cff](#citationcff)
- [DCO vs CLA](#dco-vs-cla)
- [Verify with the community profile](#verify-with-the-community-profile)

## Where GitHub looks for these files

| Fact | Rule |
|---|---|
| Recognized locations | `.github/`, repo root, or `docs/` — for CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, SUPPORT, GOVERNANCE, CODEOWNERS |
| Precedence | If a file exists in more than one location, GitHub uses the first found in the order `.github/` → root → `docs/` |
| Org-wide defaults | A repo named `.github` in the org/user account supplies default community health files to every repo that lacks its own; a repo-local file always overrides the default |
| Default branch only | GitHub reads these files from the default branch |
| LICENSE and CITATION.cff | Exceptions: put both at the repo **root** for reliable detection |

`FUNDING.yml` is the other exception: repo-locally it works **only** in `.github/`.
Prefer `.github/` for CODEOWNERS too (keeps the root sparse); root is conventional
and fine for CONTRIBUTING, SECURITY, GOVERNANCE, LICENSE, CITATION.cff.

## Right-size by project stage

Do not scaffold everything on day one. In a 10,000-repo analysis of active
repositories, README appeared in ~95% but CONTRIBUTING.md in only ~32% —
contributor docs are added when contributors exist, not before.

| Stage | Add now | Defer |
|---|---|---|
| Solo project, no outside contributors | LICENSE, README, `.gitignore`, CI | CONTRIBUTING, CODE_OF_CONDUCT, GOVERNANCE, FUNDING, CODEOWNERS |
| First outside contributors arriving | CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, SUPPORT.md (if questions land in issues) | GOVERNANCE.md beyond one page, CODEOWNERS |
| Multiple maintainers / teams | 1-page GOVERNANCE.md, CODEOWNERS (+ code-owner review rule — see security-settings sibling), FUNDING.yml if accepting money | — |
| Multi-vendor / foundation-bound | Full GOVERNANCE.md with contributor ladder, neutral ownership of trademark/domain/IP, DCO or CLA enforcement | — |
| Research software (any stage) | CITATION.cff | — |

## CONTRIBUTING.md

**Where surfaced:** linked from the repo sidebar ("Contributing"), shown as a banner
link when a user opens their first issue or PR, and counted in the community profile.

Write it for the person about to open a PR. Must contain, in this order:

1. **Dev environment setup** — exact clone/install commands, required tool versions
   (language runtime, package manager), and any one-time bootstrap step.
2. **How to run tests and linters** — the literal commands (`make check`,
   `npm test`, …). If CI runs it, the contributor must be able to run it locally.
3. **PR workflow** — branch naming, commit message convention (state if commits
   need `Signed-off-by`, see [DCO vs CLA](#dco-vs-cla)), whether an issue must be
   linked before a PR is opened, and what review to expect (who, rough turnaround).
4. **Issue reporting** — where to file bugs vs. ask questions (link SUPPORT.md),
   and a pointer to "good first issue" labels if used.
5. **Links** — code of conduct, license note ("contributions are accepted under
   the project license"), style guide if one exists.

Checklist:
- [ ] A newcomer can go from `git clone` to green tests using only this file
- [ ] Test/lint commands are copy-pasteable, not described in prose
- [ ] The PR gate policy (issue-first? sign-off?) is stated explicitly
- [ ] AI-assistance policy stated if the project has one (allowed / disclose / banned)

## CODE_OF_CONDUCT.md

**Where surfaced:** repo sidebar ("Code of conduct"), community profile, and the
new-issue/new-PR contributor banner.

- Use the **Contributor Covenant** (current version 2.1) verbatim or lightly
  adapted — it is the near-universal standard and GitHub detects it automatically
  for the community profile. Do not write a bespoke one.
- The only required edit: fill in the **enforcement contact** (a real, monitored
  email or form). An unreachable contact is worse than none.
- Adding it via GitHub's UI (`Add file` → type `CODE_OF_CONDUCT.md`) offers the
  template with the contact field prompted.
- Right-sizing: skip it for a solo scratch repo; add it as soon as you invite
  contributions — it costs one file and its absence is a visible gap in the
  community profile.

## SECURITY.md

**Where surfaced:** the repo's **Security tab** ("Security policy" →
"Report a vulnerability"), community profile, and linked when users open issues on
some flows. Docs: https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository

Must contain:

1. **A private reporting path.** Prefer GitHub Private Vulnerability Reporting
   (PVR): link `https://github.com/<owner>/<repo>/security/advisories/new`.
   **Caveat — say this in the file only after checking:** that URL returns **404
   until PVR is enabled** on the public repo (Settings → Advanced Security →
   Private vulnerability reporting). If PVR is not enabled, give a monitored
   security email instead — never let the only reporting path be a dead link.
   (Enabling PVR itself is a settings task — sibling reference.)
2. **Supported versions** — a small table of which release lines receive fixes:

   ```markdown
   | Version | Supported |
   | ------- | --------- |
   | 2.x     | yes       |
   | < 2.0   | no        |
   ```
3. **What to expect** — acknowledgment window (e.g., 72 hours), disclosure policy
   (coordinated disclosure; no public issues for vulnerabilities).
4. **Explicit instruction not to open public issues** for security reports.

## SUPPORT.md

**Where surfaced:** GitHub links SUPPORT.md prominently when a user starts creating
a **new issue**, which is exactly the moment to redirect questions.

Purpose: route usage questions **away from the issue tracker**. Keep it under a
page:

- Where to ask questions: GitHub Discussions, Discord/Slack, Stack Overflow tag,
  mailing list — pick the ones that are actually monitored, delete the rest.
- What belongs in issues (reproducible bugs, concrete feature requests) vs. what
  does not (how-do-I questions, environment debugging).
- Link to docs/FAQ first.
- If commercial support exists, one line pointing to it.

Add it as soon as questions start appearing as issues; it pairs with (does not
replace) issue templates.

## GOVERNANCE.md

**Where surfaced:** no dedicated UI slot — link it from README and CONTRIBUTING.
Its value is social, not mechanical: it answers "who decides, and how do I become
one of them" before a dispute forces the question.

**A one-page GOVERNANCE.md beats no governance.** For a small-to-mid project,
cover exactly three things:

1. **Roles** — who the maintainers are (link a team or list), what a contributor
   vs. reviewer vs. maintainer can do (triage, approve, merge, release, admin).
2. **Decision-making** — default: lazy consensus on PRs/issues; name the
   tie-breaker (lead maintainer decides / maintainer majority vote) and where
   decisions are recorded (issues, ADRs).
3. **Maintainer ladder sketch** — how someone becomes a maintainer (e.g.,
   sustained contributions + nomination by an existing maintainer + no
   objections within a week) and how inactive maintainers are retired
   (e.g., 6 months inactivity → emeritus).

Model reference (pick one, name it in the file): BDFL (single lead, fine early),
liberal contribution / consensus-seeking (Node.js/Rust style), meritocratic
ladder (Apache style), foundation-led (CNCF style — for multi-vendor projects).
Move toward foundation-style neutrality only when multiple companies contribute
competitively or one person's departure would be existential. For that stage,
also document succession basics: who holds admin/npm/PyPI/domain access.

## FUNDING.yml

**Where surfaced:** enables the **Sponsor** button at the top of the repo page.
Location: `.github/FUNDING.yml` on the default branch — GitHub documents only the
`.github/` folder for repo-local FUNDING.yml (an org/user `.github` repository can
supply the default). Docs: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository

Format — one platform key per line; values are usernames unless noted:

```yaml
# .github/FUNDING.yml — include only platforms you actually use
github: [maintainer1, maintainer2]   # up to 4 sponsored accounts
open_collective: project-slug
patreon: username
ko_fi: username
tidelift: npm/package-name           # platform-name/package-name
liberapay: username
polar: username
buy_me_a_coffee: username
thanks_dev: username
lfx_crowdfunding: project-name
issuehunt: username
custom: ["https://example.com/donate"]  # up to 4 URLs
```

Rules:
- Keys must be from the supported set above — unknown keys are ignored.
- `github` and `custom` take arrays (max 4 each); other keys take a single value.
- File must be on the default branch; the Sponsor button must also be enabled in
  repo Settings → Features → Sponsorships.
- An org-level `.github` repo FUNDING.yml provides the default for all org repos.

## CODEOWNERS

**Where surfaced:** owners are **automatically requested for review** when a PR
touches matching paths; owner names appear on hover in the file view.
Docs: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners

**State the limitation plainly: CODEOWNERS alone is INERT as a gate.** Without a
branch protection rule or ruleset enabling **"Require review from Code Owners"**,
it only auto-requests reviewers — it never blocks a merge. Write the file here;
enable the enforcement rule per the security-settings sibling reference.

Syntax (gitignore-style patterns; **last matching line wins**):

```
# .github/CODEOWNERS
*                       @org/maintainers          # default owner (first = lowest precedence)
*.py                    @org/python-reviewers
/docs/                  @org/docs-team
/src/api/               @api-lead

# Sensitive paths: whoever controls these controls CI, permissions, and automation.
# Always assign them to a small trusted set.
/.github/               @org/admins
/.github/workflows/     @org/admins
/CODEOWNERS             @org/admins
```

Rules:
- Location: `.github/`, root, or `docs/`; first found in that order wins. Max 3 MB.
- Owners: `@username`, `@org/team-name`, or a verified email. Teams must exist
  and have **explicit write access** to the repo, or the entry is ignored.
- Each pattern's owners are listed space-separated on the same line.
- The file is read from the branch the PR targets.
- Always include the sensitive-path block above: `.github/` (workflows,
  `dependabot.yml`, this file itself) is the config that defines every other
  protection — gate it behind human review by a minimal owner set.
- Errors (unknown user, team without access) are shown in the GitHub UI when
  viewing the CODEOWNERS file — check after editing.

## LICENSE

**Where surfaced:** the repo sidebar license badge, search filters, and the API —
GitHub's detector (Licensee) needs the **full, unmodified license text in a
root-level `LICENSE` file** to identify it. A license named only in the README or
`package.json` is not detected.

- Default choice: **MIT** (simplest, maximally reused). Choose **Apache-2.0**
  when an explicit patent grant matters (corporate users/contributors). Consider
  **AGPL-3.0** deliberately if preventing unreciprocated SaaS/cloud use is a
  goal — a real trend, but it costs adoption; do not drift into it by default.
- Fill in year and copyright holder in the template.
- Add SPDX identifiers where tooling reads them: `license: "MIT"` /
  `license = "MIT"` in the package manifest, and optionally
  `// SPDX-License-Identifier: MIT` headers in source files — registries and
  compliance scanners consume these, GitHub's badge does not.
- No LICENSE file = all rights reserved; nobody may legally reuse the code.
  This is the single highest-impact file on the list — never defer it.

## CITATION.cff

For research software only. Put a `CITATION.cff` (Citation File Format, YAML) at
the repo **root**; GitHub then shows a **"Cite this repository"** button in the
sidebar with APA/BibTeX export. Include at minimum `cff-version`, `message` (the
"please cite as" sentence — required by the CFF schema), `title`, `authors` (with
ORCID iDs if available), `version`, and `date-released`; add
`doi` after minting one (archive a release to Zenodo to get a DOI). Generate the
file with the cffinit web tool rather than hand-writing it, and update `version`/
`date-released` on each citable release.

## DCO vs CLA

State the project's choice in CONTRIBUTING.md. Decision table:

| Question | If yes → | Why |
|---|---|---|
| Default (no special needs)? | **DCO** — contributors add `Signed-off-by` via `git commit -s`; enforce with the DCO check app as a required status | Lowest friction, contributor keeps copyright, no relicensing power asymmetry; the direction most projects are migrating (Spring, OpenStack, ownCloud all dropped CLAs for DCO) |
| Need the option to relicense or dual-license later? | **CLA** (individual + corporate variants; enforce with CLA Assistant or LFX EasyCLA) | DCO grants no relicensing rights; only a CLA with broad grants preserves that option |
| Need an explicit patent grant / regulated-industry paper trail, corporate steward? | **CLA** | DCO certifies origin only — no patent license |
| Maintainers routinely **amend contributor commits** before merge? | Reconsider strict DCO | Each amending maintainer becomes a co-author needing their own sign-off — real process overhead for rebase-and-fix workflows; automated CLA may be less friction here |

Whichever you pick, enforce it as a required check, not by manual inspection —
and document the sign-off command in CONTRIBUTING.md so first-time contributors
are not bounced by a red X they don't understand.

## Verify with the community profile

GitHub grades public repos on these files. Check programmatically:

```bash
gh api repos/{owner}/{repo}/community/profile --jq '{health_percentage, files: (.files | keys)}'
```

- `health_percentage` reflects presence of description, README, license, code of
  conduct, contributing guide, and issue/PR templates.
- The same data backs **Insights → Community Standards** in the UI, which shows
  an add-file button for each gap.
- Target: `health_percentage` of 100 for any repo inviting contributors; for a
  solo repo, README + LICENSE is an acceptable floor.

Final checklist after adding/editing files:
- [ ] Files are on the **default branch** and in a recognized location
- [ ] SECURITY.md's reporting link actually resolves (PVR enabled, or email fallback)
- [ ] CODEOWNERS shows no errors in the GitHub file view; enforcement rule tracked separately
- [ ] Sponsor button renders if FUNDING.yml was added
- [ ] License is detected in the sidebar (full text at root)
- [ ] Community profile percentage re-checked via `gh api`
