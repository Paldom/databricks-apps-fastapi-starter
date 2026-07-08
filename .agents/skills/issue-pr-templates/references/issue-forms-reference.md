# GitHub Issue Forms, Template Config, PR Templates, and Starter Labels

Structured intake reference: YAML issue forms, `config.yml` routing, PR templates,
and a starter label set. Prose files (CONTRIBUTING, CODE_OF_CONDUCT, SECURITY) are
covered by a sibling skill — do not create them from here.

## Contents

- [Right-sizing: when to add templates](#right-sizing-when-to-add-templates)
- [File locations](#file-locations)
- [Why YAML forms beat Markdown templates](#why-yaml-forms-beat-markdown-templates)
- [Issue-forms schema cheat sheet](#issue-forms-schema-cheat-sheet)
- [bug_report.yml — annotated example](#bug_reportyml--annotated-example)
- [feature_request.yml — annotated example](#feature_requestyml--annotated-example)
- [config.yml — chooser routing](#configyml--chooser-routing)
- [Validate before committing](#validate-before-committing)
- [PR template](#pr-template)
- [Multiple PR templates: the limitation](#multiple-pr-templates-the-limitation)
- [Starter label set](#starter-label-set)
- [Intake-funnel patterns](#intake-funnel-patterns)
- [Checklist](#checklist)

## Right-sizing: when to add templates

Match template weight to real triage cost — no elaborate intake funnel for a repo
with no external reporters.

| Project stage | Do | Skip |
|---|---|---|
| Solo / no outside users yet | README, LICENSE, CI. At most a minimal PR template. | Issue forms, `config.yml`, label taxonomy |
| First outside bug reports arriving | `bug_report.yml` + `config.yml` routing questions to Discussions | Multiple PR templates, elaborate dropdowns |
| Steady contributor volume | Full set below: both forms, labels, PR checklist, issue-first rule in the PR template | — |

Templates exist to cut triage round-trips ("what version?", "how do I reproduce
this?"). Until those round-trips happen, templates are friction with no payoff.

## File locations

```
.github/
├── ISSUE_TEMPLATE/
│   ├── bug_report.yml        # YAML issue form (extension .yml or .yaml)
│   ├── feature_request.yml
│   └── config.yml            # template-chooser config (this exact name)
└── PULL_REQUEST_TEMPLATE.md   # single default PR template
```

- Issue forms only take effect from the **default branch**.
- Filenames other than `config.yml` are arbitrary; the chooser lists templates
  **alphabetically by filename** — prefix with digits (`1-bug.yml`, `2-feature.yml`)
  to control order.
- Legacy Markdown issue templates (`.md`) can coexist in the same directory; prefer
  forms for anything new.
- GitHub also honors `PULL_REQUEST_TEMPLATE.md` in the repo root or `docs/`; use
  `.github/` to keep the root clean.

## Why YAML forms beat Markdown templates

| Capability | Markdown template | YAML issue form |
|---|---|---|
| Required fields enforced before submit | No — users delete the scaffolding | Yes (`validations.required`) |
| Structured inputs (dropdowns, checkboxes) | No | Yes |
| Auto-apply labels/assignees | Frontmatter only, easily bypassed | Yes, reliably on submit |
| Machine-readable responses (each field renders as a titled section) | No | Yes — automation can parse sections |
| Code/log fields auto-fenced | No — users paste unformatted logs | Yes (`render: shell`) |

Forms directly reduce the "it's broken, please fix" issue class: the reporter
cannot submit without a version and repro steps.

## Issue-forms schema cheat sheet

Verified against the documented syntax:
<https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms>

Top-level keys:

| Key | Required | Notes |
|---|---|---|
| `name` | yes | Shown in chooser; must be unique across templates |
| `description` | yes | Chooser subtitle |
| `body` | yes | Array of form elements; at least one non-`markdown` element |
| `title` | no | Default issue title prefill, e.g. `"[Bug]: "` |
| `labels` | no | Array or comma-separated string; **create the labels first** — nonexistent labels are not applied |
| `assignees` | no | String or array of usernames |
| `type` | no | Organization issue type name |
| `projects` | no | `OWNER/PROJECT-NUMBER`; only applied when the submitter has write access |

Body element types (`type:` on each entry):

| Type | Purpose | Key attributes | Validations |
|---|---|---|---|
| `markdown` | Display-only text; **not included** in the submitted issue | `value` (required) | — |
| `input` | Single-line text | `label` (required), `description`, `placeholder`, `value` | `required` |
| `textarea` | Multi-line text | `label` (required), `description`, `placeholder`, `value`, `render` (language name; fences the response as a code block) | `required` |
| `dropdown` | Pick from options | `label` (required), `options` (required, unique, must not contain literal `"None"`), `multiple`, `default` (option index) | `required` |
| `checkboxes` | Checklist | `label` (required), `description`, `options` (array of `{label, required}`) | per-option `required` |

`id` rules: optional on every element; if set, only alphanumeric plus `-` and `_`,
and unique within the form. Set ids on fields automation will read.

## bug_report.yml — annotated example

```yaml
# .github/ISSUE_TEMPLATE/1-bug.yml
name: Bug report
description: Report something that is broken or behaving unexpectedly.
title: "[Bug]: "
labels: ["bug", "needs-triage"]      # auto-applied on submit; labels must already exist
body:
  - type: markdown                    # guidance only — never appears in the issue
    attributes:
      value: |
        Thanks for the report. Search existing issues first — duplicates are closed.

  - type: checkboxes
    id: preflight
    attributes:
      label: Preflight
      options:
        - label: I searched existing issues and this is not a duplicate.
          required: true              # blocks submission until checked

  - type: input
    id: version
    attributes:
      label: Version
      description: Exact release or commit SHA.
      placeholder: "v1.4.2"
    validations:
      required: true                  # the field that kills "what version?" round-trips

  - type: dropdown
    id: os
    attributes:
      label: Operating system
      options:                        # do NOT include a literal "None" option
        - macOS
        - Linux
        - Windows
        - Other
    validations:
      required: true

  - type: textarea
    id: repro
    attributes:
      label: Steps to reproduce, expected vs. actual behavior
      description: Minimal, complete steps. Issues without repro steps get closed as needs-repro.
      placeholder: |
        1. Run `...`
        2. Observe `...`; expected `...`
    validations:
      required: true

  - type: textarea
    id: logs
    attributes:
      label: Relevant log output
      description: Paste raw logs — automatically formatted, no backticks needed.
      render: shell                   # fences the response as ```shell — keeps logs readable
    validations:
      required: false
```

## feature_request.yml — annotated example

```yaml
# .github/ISSUE_TEMPLATE/2-feature.yml
name: Feature request
description: Propose a new capability or improvement.
title: "[Feature]: "
labels: ["enhancement", "needs-triage"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem to solve
      description: What can't you do today? Describe the problem, not the solution.
    validations:
      required: true                  # forces problem-first framing, filters drive-by wishes

  - type: textarea
    id: proposal
    attributes:
      label: Proposed solution
    validations:
      required: true

  - type: dropdown
    id: contribution
    attributes:
      label: Are you willing to contribute this feature?
      options:
        - Yes, I can open a PR
        - Yes, with guidance
        - No
    validations:
      required: true                  # surfaces potential contributors at intake time
```

## config.yml — chooser routing

```yaml
# .github/ISSUE_TEMPLATE/config.yml
blank_issues_disabled: true           # hides "Open a blank issue" in the chooser
contact_links:
  - name: Questions & ideas
    url: https://github.com/OWNER/REPO/discussions
    about: Ask questions and discuss ideas in Discussions — the issue tracker is for actionable bugs and features.
  - name: Report a security vulnerability
    url: https://github.com/OWNER/REPO/security/advisories/new
    about: Never open a public issue for security problems. Use a private security advisory.
```

- `blank_issues_disabled: true` removes the blank-issue option from the chooser UI;
  determined users can still reach the blank form via direct URL, so treat it as a
  strong nudge, not a hard gate.
- Route **questions to Discussions** and **vulnerabilities to private security
  advisories** — the two categories that most pollute an issue tracker.
- `contact_links` entries appear below the templates in the chooser.

## Validate before committing

Issue forms fail silently-ish (GitHub shows a YAML error banner on the chooser, but
you only see it after pushing). Validate locally against the vendored schema:

```bash
pip install check-jsonschema==0.36.2
check-jsonschema --builtin-schema vendor.github-issue-forms .github/ISSUE_TEMPLATE/*.yml
```

If `config.yml` trips the schema (it is not an issue form), exclude it from the
glob: `$(ls .github/ISSUE_TEMPLATE/*.yml | grep -v config.yml)`. Wire the command
into CI or a pre-commit hook so template edits cannot break the chooser.

## PR template

PR templates are **Markdown only** — there is no YAML form equivalent for PRs.
A solid default:

```markdown
<!-- .github/PULL_REQUEST_TEMPLATE.md -->
## Summary

<!-- What does this change and why? One or two sentences. -->

## Linked issue

<!-- Required for non-trivial changes. Use a closing keyword. -->
Closes #

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Docs / chore

## Checklist

- [ ] Tests added or updated for the change
- [ ] Docs updated (README / docs site) if behavior changed
- [ ] Changelog entry added (if the project keeps one)
- [ ] CI passes locally (`make check` or project equivalent)
- [ ] Self-reviewed the diff before requesting review
```

Keep it short — long PR templates get deleted wholesale. The checklist is a
reviewer contract: tests, docs, changelog, linked issue.

## Multiple PR templates: the limitation

GitHub supports a `.github/PULL_REQUEST_TEMPLATE/` directory with multiple
templates (`feature.md`, `bugfix.md`, `docs.md`), **but there is no picker UI** —
unlike issues, contributors are never shown a template chooser. Workarounds:

- **Query parameter** on the compare/PR URL:
  `https://github.com/OWNER/REPO/compare/main...branch?quick_pull=1&template=bugfix.md`
  — document these links in CONTRIBUTING or pin them; they are the only web-UI path.
- **GitHub CLI**: `gh pr create --template bugfix.md`.
- Without one of the above, contributors get the single default
  `PULL_REQUEST_TEMPLATE.md` (or none).

Recommendation: use **one** default PR template. Adopt the folder + query-param
scheme only when change types genuinely need different checklists and you are
willing to maintain the documented links.

## Starter label set

GitHub pre-creates the first nine below in new repos; keep their names — tooling
and contributors expect them. Add the last two for triage flow. Create any label
**before** referencing it in a form's `labels:` key.

| Label | Color | Description |
|---|---|---|
| `bug` | `#d73a4a` | Something isn't working |
| `documentation` | `#0075ca` | Improvements or additions to documentation |
| `duplicate` | `#cfd3d7` | This issue or pull request already exists |
| `enhancement` | `#a2eeef` | New feature or request |
| `good first issue` | `#7057ff` | Good for newcomers |
| `help wanted` | `#008672` | Extra attention is needed |
| `invalid` | `#e4e669` | This doesn't seem right |
| `question` | `#d876e3` | Further information is requested |
| `wontfix` | `#ffffff` | This will not be worked on |
| `needs-triage` | `#ededed` | Awaiting maintainer triage (auto-applied by forms) |
| `needs-repro` | `#fbca04` | Cannot reproduce yet; reporter action needed |

Create missing ones with the CLI:

```bash
gh label create needs-triage --color ededed --description "Awaiting maintainer triage"
gh label create needs-repro  --color fbca04 --description "Cannot reproduce yet; reporter action needed"
```

Why the exact names matter:

- **`good first issue`** — GitHub surfaces these issues algorithmically: they
  populate the repo's `/contribute` page and the `good-first-issues:>0` search
  qualifier. Name must match exactly (case-insensitive).
- **`help wanted`** — powers the `help-wanted-issues:>0` qualifier and signals
  contribution-readiness to discovery surfaces.

## Intake-funnel patterns

Templates are one stage of a funnel that keeps maintainer attention for work that
is ready for it. Adopt incrementally, in this order:

1. **Required form fields** (above) — eliminates the largest class of unusable
   reports at the door.
2. **Chooser routing** — `blank_issues_disabled` plus contact links push questions
   to Discussions and vulnerabilities to private advisories.
3. **Issue-first PRs** — state in the PR template and CONTRIBUTING that
   non-trivial PRs must link an accepted issue; close unlinked feature PRs with a
   pointer to the rule. This is the single most-adopted gate against low-effort
   and AI-generated drive-by PRs.
4. **Duplicate hygiene** — a required "I searched existing issues" checkbox plus
   GitHub's built-in duplicate detection at creation; close duplicates with a link.
5. **Stale policies** — auto-label and close issues that never answered a
   `needs-repro` request. Keep grace windows generous; the goal is signal, not speed.

Keep gates configurable and documented — blanket restrictions disproportionately
hit good-faith first-time contributors.

## Checklist

- [ ] `.github/ISSUE_TEMPLATE/1-bug.yml` and `2-feature.yml` exist, with
      `validations.required` on version/repro/problem fields
- [ ] Forms auto-apply `labels:` that already exist in the repo
- [ ] Log fields use `render: shell`
- [ ] `config.yml` disables blank issues and routes questions + security reports
- [ ] `check-jsonschema --builtin-schema vendor.github-issue-forms` passes on all forms
- [ ] Single `.github/PULL_REQUEST_TEMPLATE.md` with tests/docs/changelog/linked-issue checklist
- [ ] `good first issue` and `help wanted` labels exist with exact names
- [ ] Template weight matches actual triage volume (see right-sizing table)
