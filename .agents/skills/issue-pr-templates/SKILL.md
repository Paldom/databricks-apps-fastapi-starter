---
name: issue-pr-templates
description: Builds structured GitHub contribution intake - YAML issue forms with required fields and auto-labels, config.yml routing, a pull request template with a working checklist, and starter labels like good first issue. Use when the user asks for issue templates, bug report forms, a PR template, or to stop blank issues. Not for CONTRIBUTING or other prose community files, and not for issue triage.
license: MIT
argument-hint: [bug|feature|pr|labels|all]
---

# issue-pr-templates

Builds the structured intake layer that turns "it's broken, please fix" into
actionable reports. The failure this skill fixes: models write legacy Markdown
issue templates (no required fields), get the YAML forms schema subtly wrong
(forms silently don't render), and forget `config.yml` routing entirely.

## When NOT to use

- CONTRIBUTING/SECURITY/SUPPORT prose files → `community-health`.
- Triaging or closing existing issues, stale-bot automation → out of scope.
- Requiring PR reviews/checks before merge → `repo-protections`.
- Configuring GitHub Discussions itself → out of scope (linking to it is in scope).

## Workflow

1. **Read `references/issue-forms-reference.md`** for the exact schema and the
   annotated examples — do not write forms from memory.
2. **Issue forms** in `.github/ISSUE_TEMPLATE/`:
   - `bug_report.yml` — required version + repro-steps fields, environment dropdown
     where sensible, `render: shell` for logs, auto-label `bug`.
   - `feature_request.yml` — problem-first fields (what/why before how), label
     `enhancement`.
   - Only `.yml`/`.yaml` files in that exact directory render; forms only work on
     the default branch.
3. **`config.yml`**: `blank_issues_disabled: true` plus `contact_links` routing
   questions to Discussions/SUPPORT and security reports to private reporting —
   never to a public issue form.
4. **PR template**: single `.github/PULL_REQUEST_TEMPLATE.md`, short actionable
   checklist (tests run, docs updated, linked issue, no `.local`/secret files).
   If multiple PR templates are requested: GitHub has no picker UI — explain the
   `?template=name.md` query-param workaround and recommend one good default.
5. **Labels**: create the ones the forms reference plus the newcomer set:
   ```bash
   gh label create "good first issue" --color 7057ff --description "Good for newcomers" --force
   gh label create "help wanted" --color 008672 --description "Extra attention is needed" --force
   ```
   `good first issue` is surfaced algorithmically by GitHub to newcomers — use it
   honestly or it backfires.
6. **Validate** (deterministic gate):
   ```bash
   bash "${CLAUDE_SKILL_DIR}/scripts/validate_forms.sh"
   ```
   It runs `check-jsonschema --builtin-schema vendor.github-issue-forms` against
   every form (pinned install if missing) and fails on schema violations.

## Output spec

Forms + config.yml + PR template in `.github/`, schema-valid (script exits 0),
every referenced label exists, required fields limited to what reporters can
actually answer (required-everything forms deter reports).

## Gotchas

- `config.yml` is **not** an issue form — it has a different schema; never pass it
  to the forms validator (the script already excludes it).
- A form that doesn't render usually means: wrong directory, `.md` instead of
  `.yml`, not on the default branch, or a schema violation — check in that order.
- Every `id` must be unique and `[a-z0-9-_]`; `label` values inside body elements
  are user-visible — write them as questions a reporter understands.
- Right-size: a solo project with 2 issues/month needs one bug form at most;
  elaborate intake before there's traffic is friction without benefit.

## Files

- `references/issue-forms-reference.md` — schema, annotated examples, config.yml,
  PR template, label set, validation command.
- `scripts/validate_forms.sh` — schema validation with pinned check-jsonschema;
  non-zero exit on invalid forms.
