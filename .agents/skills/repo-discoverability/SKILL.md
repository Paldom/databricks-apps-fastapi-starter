---
name: repo-discoverability
description: Optimizes how a GitHub repository gets found - repo description, topics, social preview image, name/H1 alignment, heading and link practices for GitHub and web search. Use when the user wants more stars, traffic, or search visibility, or asks to set topics, improve repo SEO, or make the project easier to find. Not for rewriting README prose or repo protections.
license: MIT
argument-hint: [owner/repo (defaults to current repo)]
---

# repo-discoverability

Tunes the **metadata layer** GitHub actually ranks and displays: repository
description, topics, social preview, homepage, and the naming/heading signals
search engines read. Models asked to "improve SEO" tend to keyword-stuff README
prose; the real levers are repo settings most people never touch — this skill
works those levers, with `gh` commands for each.

## When NOT to use

- Writing or restructuring README content → `readme-author`.
- Community files, templates, protections → their focused skills.
- Building a docs website (that's the web-tier; this skill only points to it).
- Promotion/marketing advice (where to post) → out of scope.

## Workflow

1. **Audit current state** (read-only):
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/check_discoverability.py" [owner/repo]
   ```
   It reports description, topics, homepage, social preview, and H1 alignment
   status with pass/warn/fail per lever.
2. **Read `references/discoverability-playbook.md`**, then fix in priority order:
   - **Description** (the About text *and* the search snippet): one sentence with
     plain category keywords + audience + outcome. ≤350 chars.
     `gh repo edit <owner/repo> --description "..."`
   - **Topics**: 5–10, covering category, language, use case, domain. Lowercase,
     hyphens, ≤35 chars each, only accurate ones — topics are browsable search
     surfaces, not tags for decoration.
     `gh repo edit <owner/repo> --add-topic <t1> --add-topic <t2> ...`
   - **Name ↔ H1 alignment**: README H1 should match or contain the repo name; if
     the repo name is cryptic, compensate in the description's first words.
   - **Homepage**: docs/demo URL if one exists: `gh repo edit --homepage <url>`.
   - **Social preview**: cannot be set via CLI — tell the user exactly:
     Settings → General → Social preview (1280×640; without it, shared links render
     as bare name + avatar).
   - **Headings/links** (hand off content edits to `readme-author` if substantial):
     task-based `##` headings; descriptive anchor text, never "click here".
3. **Apply only after showing the user** the before → after for description and
   topics; then re-run the check script to confirm.
4. **Two-tier reminder**: full search control (title tags, meta descriptions,
   structured data) lives on a docs/Pages site, not the repo page. Say so when the
   user's ambitions exceed what repo metadata can do.

## Output spec

Description, topics, and homepage set and verified via re-run of the check script;
social-preview instruction delivered; any README-level naming misalignment either
fixed (trivial) or delegated to `readme-author`. No inaccurate topic added.

## Gotchas

- Private repos are invisible to search — prepare metadata anyway so the public
  flip is turnkey, and say that's what you're doing.
- GitHub search favors maintained repos: freshness (recent commits/releases) is a
  ranking signal no metadata can fake.
- Vendor-blog conversion stats ("N× more stars") are directional at best — never
  promise numbers.
- Keyword stuffing violates the people-first rule and reads as spam in the About
  box — every topic and keyword must be defensible.

## Files

- `references/discoverability-playbook.md` — the two-tier model, per-lever guidance,
  effort/return table, measurement (14-day traffic windows, views vs clones).
- `scripts/check_discoverability.py` — read-only audit via `gh`; non-zero exit when
  required levers are missing.
