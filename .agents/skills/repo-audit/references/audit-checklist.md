# Repo Audit Checklist — Weighted, Scoreable (100 points)

Audit how professional an open-source GitHub repository looks and behaves. Six
categories mirror the sibling skills; each check names the skill that owns the
fix. This file scores and routes — it does NOT teach how to fix. Load the owner
skill for remediation.

## Contents

- [How to run the audit](#how-to-run-the-audit)
- [Category 1 — README quality (25 pts)](#category-1--readme-quality-25-pts)
- [Category 2 — Discoverability & metadata (15 pts)](#category-2--discoverability--metadata-15-pts)
- [Category 3 — Community health files (20 pts)](#category-3--community-health-files-20-pts)
- [Category 4 — Contribution intake (10 pts)](#category-4--contribution-intake-10-pts)
- [Category 5 — Protections (15 pts)](#category-5--protections-15-pts)
- [Category 6 — Vital signs (15 pts)](#category-6--vital-signs-15-pts)
- [Scoring rubric](#scoring-rubric)
- [Right-sizing: which checks to defer](#right-sizing-which-checks-to-defer)
- [Report output template](#report-output-template)

## How to run the audit

1. Set the target: `OWNER=<owner> REPO=<repo>`; get the default branch with
   `gh repo view "$OWNER/$REPO" --json defaultBranchRef -q .defaultBranchRef.name`.
2. Pull the bulk data once, then score each check from it:

```bash
# Repo metadata (feeds categories 2, 3, 6)
gh repo view "$OWNER/$REPO" --json name,description,homepageUrl,repositoryTopics,licenseInfo,hasIssuesEnabled,hasDiscussionsEnabled,isArchived,pushedAt,latestRelease,defaultBranchRef

# Community profile (public repos only; feeds category 3)
gh api "repos/$OWNER/$REPO/community/profile"

# Clone shallow for file checks (feeds categories 1, 4, 5)
git clone --depth 1 "https://github.com/$OWNER/$REPO" /tmp/audit-$REPO
```

3. Score every check as pass (full points), partial (where a graded split is
   given), or fail (0). Mark inapplicable checks `N/A` and rescale (see
   [Scoring rubric](#scoring-rubric)).
4. **Evidence boundary.** `scripts/collect_evidence.py` answers the mechanical
   checks and lists the rest under `not_collected`. Three states, three duties:
   evidence `true/false/number` → score it; evidence `null` → report **unknown**
   (never a fail); check is manual/agent-judged (secret-history scan, personal-file
   review, prose quality, topic relevance, responsiveness) → read the repo and say
   you judged it, or mark it "manual review required". Never score from silence.
5. Emit the report using the [template](#report-output-template). Rank fixes by
   `points lost x ease of fix`, and name the owner skill on every fix.

Context for calibration: in a 10,000-repo analysis of active repositories,
README appeared in 95.3%, `.gitignore` in 95.0%, a `.github/` directory in
82.5%, LICENSE in 73.1%, and CONTRIBUTING in only 31.7%. Missing README or
LICENSE is therefore a glaring defect; missing CONTRIBUTING is merely a gap.

---

## Category 1 — README quality (25 pts)

**Fixes owned by: `readme-author` skill.** Do not rewrite the README here —
score it, then route.

| # | Check | Pts | Pass criterion |
|---|-------|----:|----------------|
| R1 | README exists, non-stub | 6 | `README.md` at repo root, ≥ 150 words of real content (not template placeholders) |
| R2 | First screen answers what/why/how | 4 | H1 matches repo name; one-sentence value proposition directly under it; a reader can answer "what is this, why care, how do I try it" from the first screen. Graded: 4 all three / 2 partial / 0 |
| R3 | Copy-pasteable quick start | 5 | Install command AND a smallest-working usage example in fenced code blocks; no "see the docs to install" |
| R4 | Badges are signals, not a wall | 2 | 3–5 badges (CI, version, license, coverage class); none broken; 0 pts for a badge wall (>8) or decorative-only badges |
| R5 | Visual proof | 2 | Screenshot/GIF/demo link for anything with a UI or CLI output; `N/A` for pure libraries with no visual surface |
| R6 | Navigable structure | 3 | Task-based headings (Installation, Usage, ...). GitHub auto-generates a TOC from headings, so heading quality is navigation quality. Long READMEs (> ~400 lines) link out instead of scrolling forever |
| R7 | Depth deferred | 3 | Deep reference lives in `docs/`, a wiki, or a site — not inlined. GitHub truncates rendered README content above 500 KiB, so oversize is a silent failure, not a style choice |

Evaluate with:

```bash
f=/tmp/audit-$REPO/README.md
test -f "$f" && wc -w "$f" && wc -l "$f"          # R1, R6, R7
head -n 30 "$f"                                    # R2 (read it)
grep -c '```' "$f"                                 # R3 (fenced blocks exist)
grep -oE '!\[[^]]*\]\([^)]*\)' "$f" | wc -l        # R4/R5 (image + badge count)
gh api "repos/$OWNER/$REPO/readme" -q .size        # R7 (bytes; 512000 = truncation)
```

## Category 2 — Discoverability & metadata (15 pts)

**Fixes owned by: `repo-discoverability` skill.**

| # | Check | Pts | Pass criterion |
|---|-------|----:|----------------|
| D1 | Description set | 5 | Repo "About" description present, benefit-led, ≤ ~120 chars, contains the terms someone would search for. Graded: 5 good / 2 present-but-vague / 0 empty |
| D2 | Topics set | 5 | 5–20 relevant topics (language, domain, problem). Graded: 5 for ≥5 relevant / 2 for 1–4 / 0 none |
| D3 | Homepage URL | 2 | Docs site, demo, or package page set as homepage |
| D4 | Social preview image | 3 | Custom Open Graph image uploaded, so shared links do not render as bare avatar + repo name |

Evaluate with:

```bash
gh repo view "$OWNER/$REPO" --json description,homepageUrl \
  --jq '{description, homepageUrl}'                                   # D1, D3
gh repo view "$OWNER/$REPO" --json repositoryTopics \
  --jq '.repositoryTopics | length'                                   # D2
gh api graphql -f query='query{repository(owner:"'$OWNER'",name:"'$REPO'"){
  usesCustomOpenGraphImage openGraphImageUrl}}'                       # D4
```

## Category 3 — Community health files (20 pts)

**Fixes owned by: `community-health` skill.** GitHub surfaces these files in
the repo sidebar and counts them in the community profile — presence is
mechanical to verify.

| # | Check | Pts | Pass criterion |
|---|-------|----:|----------------|
| C1 | LICENSE detected | 6 | Root `LICENSE` file with full text of a known license, detected by GitHub (`licenseInfo` non-null, not "Other"). No license = nobody can legally reuse the code |
| C2 | CONTRIBUTING | 4 | `CONTRIBUTING.md` covering dev setup, test command, and PR workflow (not a one-liner) |
| C3 | CODE_OF_CONDUCT | 3 | Present (Contributor Covenant or equivalent); detected in community profile |
| C4 | SECURITY policy | 3 | `SECURITY.md` (root, `.github/`, or `docs/`) with a private vulnerability-reporting path |
| C5 | Question routing | 2 | `SUPPORT.md` present or Discussions enabled, so questions have somewhere to go besides the issue tracker |
| C6 | Community profile complete | 2 | `health_percentage` == 100 on the community profile API (cross-check on C1–C3 plus templates) |

Evaluate with:

```bash
gh api "repos/$OWNER/$REPO/community/profile" \
  --jq '{health_percentage, files: (.files | with_entries(.value = (.value != null)))}'  # C1-C3, C6
gh api "repos/$OWNER/$REPO/license" -q .license.spdx_id                # C1
for p in SECURITY.md .github/SECURITY.md docs/SECURITY.md; do
  gh api "repos/$OWNER/$REPO/contents/$p" -q .path 2>/dev/null; done   # C4
gh repo view "$OWNER/$REPO" --json hasDiscussionsEnabled               # C5
```

Reference: GitHub's community profile checklist is documented at
<https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories>.

## Category 4 — Contribution intake (10 pts)

**Fixes owned by: `issue-pr-templates` skill.**

| # | Check | Pts | Pass criterion |
|---|-------|----:|----------------|
| I1 | Issue templates exist | 3 | `.github/ISSUE_TEMPLATE/` with at least bug-report and feature-request templates |
| I2 | YAML issue forms | 3 | Templates are `*.yml` issue forms (schema: `name`, `description`, `body:` with typed fields) using `validations: required: true` on repro/version fields — not free-text markdown. Graded: 3 forms-with-required / 1 markdown templates / 0 none |
| I3 | Template chooser config | 1 | `.github/ISSUE_TEMPLATE/config.yml` sets `blank_issues_enabled` deliberately and routes questions via `contact_links` |
| I4 | PR template | 2 | `.github/pull_request_template.md` (or `PULL_REQUEST_TEMPLATE/` folder) with a review checklist |
| I5 | Newcomer labels | 1 | `good first issue` label exists (GitHub surfaces it to newcomers) and is applied to at least one open issue on active repos |

Evaluate with:

```bash
ls /tmp/audit-$REPO/.github/ISSUE_TEMPLATE/ 2>/dev/null                # I1-I3
grep -l 'required: true' /tmp/audit-$REPO/.github/ISSUE_TEMPLATE/*.yml 2>/dev/null  # I2
ls /tmp/audit-$REPO/.github/pull_request_template.md \
   /tmp/audit-$REPO/.github/PULL_REQUEST_TEMPLATE/ 2>/dev/null         # I4
gh label list -R "$OWNER/$REPO" --search "good first issue"            # I5
```

## Category 5 — Protections (15 pts)

**Fixes owned by: `repo-protections` skill.**

| # | Check | Pts | Pass criterion |
|---|-------|----:|----------------|
| P1 | Default branch protected | 5 | A ruleset (or classic branch protection) on the default branch requires a PR and blocks force-push and deletion. Graded: 5 full / 2 partial (e.g. force-push blocked but direct pushes allowed) / 0 none |
| P2 | Required status checks | 3 | Merge is gated on CI passing (required status checks configured in the ruleset/protection) |
| P3 | Secret scanning + push protection | 3 | `security_and_analysis` shows secret scanning AND push protection enabled (free for public repos) |
| P4 | Dependabot, safely configured | 3 | Security updates enabled; if `dependabot.yml` exists, it uses `cooldown` (minimum package age) and does NOT blanket auto-merge bot PRs — bot-authored updates still pass CI and review. Graded: 3 / 1 (enabled, no cooldown) / 0 |
| P5 | CODEOWNERS gates automation config | 1 | `CODEOWNERS` exists and covers `.github/` (workflows + dependabot config get human review) |

Evaluate with:

```bash
BR=$(gh repo view "$OWNER/$REPO" --json defaultBranchRef -q .defaultBranchRef.name)
gh api "repos/$OWNER/$REPO/rules/branches/$BR" --jq '[.[].type]'      # P1, P2 (effective rules, no admin needed)
gh api "repos/$OWNER/$REPO/rulesets" --jq '.[].name' 2>/dev/null      # P1 (ruleset inventory)
gh api "repos/$OWNER/$REPO" \
  --jq '.security_and_analysis | {secret_scanning: .secret_scanning.status,
        push_protection: .secret_scanning_push_protection.status}'    # P3
gh api "repos/$OWNER/$REPO/vulnerability-alerts" >/dev/null 2>&1 \
  && echo "dependabot-alerts: enabled" || echo "disabled/unknown"     # P4
grep -E 'cooldown|open-pull-requests-limit' /tmp/audit-$REPO/.github/dependabot.yml 2>/dev/null  # P4
grep -E '^\s*/?\.github/' /tmp/audit-$REPO/.github/CODEOWNERS \
     /tmp/audit-$REPO/CODEOWNERS 2>/dev/null                          # P5
```

Note: `rulesets` and `security_and_analysis` fields may require push/admin
access; if a call 403s, score from the effective-rules endpoint and mark the
check `unverifiable` rather than failing it.

## Category 6 — Vital signs (15 pts)

**Fixes owned by: the maintainer (no sibling skill).** These reflect ongoing
project behavior, not one-time file changes — the report should say so instead
of routing to a skill.

| # | Check | Pts | Pass criterion |
|---|-------|----:|----------------|
| V1 | Recent activity | 4 | Not archived; pushed within the last 90 days. Graded: 4 / 2 (≤ 12 months) / 0 |
| V2 | CI exists and is green | 4 | At least one workflow in `.github/workflows/`; latest run on the default branch succeeded. Graded: 4 green / 2 CI exists but red or flaky / 0 no CI |
| V3 | Releases | 3 | Tagged releases with release notes; latest release is not far behind the default branch on an actively developed repo |
| V4 | Triage responsiveness | 2 | Open issues/PRs show maintainer responses; no large backlog of months-old untouched PRs |
| V5 | Change history | 2 | `CHANGELOG.md` maintained, or releases carry generated notes |

Evaluate with:

```bash
gh repo view "$OWNER/$REPO" --json isArchived,pushedAt                 # V1
gh run list -R "$OWNER/$REPO" --branch "$BR" --limit 3 \
  --json conclusion,workflowName                                       # V2
gh release list -R "$OWNER/$REPO" --limit 3                            # V3
gh pr list -R "$OWNER/$REPO" --state open --limit 20 --json updatedAt  # V4
gh issue list -R "$OWNER/$REPO" --state open --limit 20 --json updatedAt,comments  # V4
test -f /tmp/audit-$REPO/CHANGELOG.md && echo changelog                # V5
```

---

## Scoring rubric

Sum earned points across all six categories. For `N/A` checks, rescale:
`score = earned / (100 - na_points) * 100`, rounded to the nearest integer.

| Grade | Score | Reading |
|-------|-------|---------|
| **A** | ≥ 90 | Professional; ready for contributors and scrutiny |
| **B** | ≥ 75 | Solid; a handful of targeted fixes from A |
| **C** | ≥ 55 | Functional but visibly unpolished; prioritized fix list needed |
| **D** | < 55 | Foundational gaps; fix category-by-category, basics first |

Also report per-category scores — a B overall can hide a 0/15 in Protections,
which matters more than the letter grade.

## Right-sizing: which checks to defer

Do NOT push every repo toward 100. Match the target to the repo's stage, and
say explicitly in the report which failed checks are *deferred by design*
rather than defects. Grade against the applicable set (mark deferred checks
`N/A` and rescale) — a solo project with a great README, LICENSE, and green CI
should score well.

| Repo stage | Must pass | Reasonable to defer |
|------------|-----------|---------------------|
| Solo / early (no outside contributors yet) | R1–R3, C1, D1–D2, V2, P3, `.gitignore` | C2–C3, C5, all of Category 4, P1–P2, P5, D4, V3–V5 |
| Expecting contributors | + C2, C4, I1, I4, P1, V3 | I2–I3, I5, C3 (until community size warrants), P5 |
| Established / org-owned / flagship | Everything | Nothing — full checklist applies |

Two principles behind the table:

- **CI before governance boilerplate.** Working tests and a green badge earn
  more trust for an early project than a code of conduct nobody triggers yet.
  The prevalence data agrees: CONTRIBUTING sits at ~32% even among active
  repos, while README/.gitignore are near-universal.
- **Never defer the safety floor**: LICENSE, secret scanning + push
  protection, and a non-stub README are cheap and protect users on day one.

## Report output template

Emit the audit result in this shape (fill every bracket; drop the N/A column
if unused):

```markdown
# Repo audit: OWNER/REPO — Grade: [A-D] ([score]/100)

Stage assumed: [solo | expecting-contributors | established] (affects deferrals)

| Category | Score | Owner of fixes |
|----------|-------|----------------|
| 1. README quality        | [x]/25 | readme-author |
| 2. Discoverability       | [x]/15 | repo-discoverability |
| 3. Community health      | [x]/20 | community-health |
| 4. Contribution intake   | [x]/10 | issue-pr-templates |
| 5. Protections           | [x]/15 | repo-protections |
| 6. Vital signs           | [x]/15 | maintainer (ongoing) |

## Top 5 fixes (highest points-per-effort first)

1. [check id + one-line defect] — +[pts] pts → fix with `[owner skill]`
2. ...
3. ...
4. ...
5. ...

## Deferred by design (not defects at this stage)
- [check id]: [why deferred]

## Unverifiable (insufficient permissions)
- [check id]: [which API call failed; how to verify manually]
```

Rules for the report:

- Rank the top-5 by points recovered per unit of effort; file-presence fixes
  (LICENSE, SECURITY.md, templates) are near-zero effort and usually rank
  high.
- Every fix line names exactly one owner skill; never inline the remediation
  steps in the audit report.
- If two checks fail in the same category, still list them as separate fixes —
  the owner skill decides how to batch them.
- Do not quote engagement multipliers ("Nx more stars/contributors") as fact
  in reports; no such figure has a verifiable methodology. Justify fixes by
  the documented mechanism instead (e.g. topics feed GitHub search; the
  community profile checklist surfaces gaps to visitors).
