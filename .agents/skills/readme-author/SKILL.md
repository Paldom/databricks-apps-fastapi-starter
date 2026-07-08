---
name: readme-author
description: Writes, restructures, or syncs a professional GitHub project README - front-loaded value prop, minimal badges, copy-pasteable quick start, scannable structure for a library, CLI, or web app. Use when the user asks to write, improve, restructure, or review a README, or calls it bloated, stale, or outdated. Not for repo topics/social-preview metadata, community files, or profile READMEs.
license: MIT
argument-hint: [path-to-README or project description]
---

# readme-author

Produces READMEs that work as a landing page: a visitor should know **what this is,
why they should care, and how to try it** within the first screen. Default model
output fails at this in predictable ways — verbose prose walls, badge spam,
marketing hype, invented install commands — and this skill exists to prevent
exactly those failures.

## When NOT to use

- Repo description, topics, social preview, search visibility → `repo-discoverability`.
- CONTRIBUTING/SECURITY/SUPPORT and other community files → `community-health`.
- Personal profile READMEs (`github.com/user/user`) → out of scope; keep those to a
  single screen and decline politely.
- API reference documentation or docs sites → ordinary docs work, not this skill.

## Workflow

1. **Inspect before writing.** Read the repo: language, real install path
   (`pyproject.toml`, `package.json`, `Cargo.toml`, Makefile…), real run/test
   commands, existing docs, CI workflow names. Every command in the README must be
   copy-pasteable and true — never invent installation steps.
2. **Pick the shape.** Read `references/readme-playbook.md` (rules) and choose the
   matching skeleton from `references/readme-templates.md` (library / CLI / web app).
3. **Write front-loaded.** Order: H1 → one-line value proposition → 3–5 trust
   badges → proof (screenshot/GIF/demo link, if assets exist) → copy-pasteable
   install → smallest-success usage → features/API overview → links out for depth →
   contributing/support/license stubs that link to files.
   - One-liner: what it is + who it's for + the outcome, in plain category words.
   - Intro block ≤ ~120 words. Whole README ~200–800 words (small tool) to
     ~500–1500 (library); depth goes to `docs/` links, not inline.
   - Badges: CI, license (static shields badge), version/coverage only if real.
     Verify the workflow file exists before adding its badge.
   - Write for a global audience (short simple sentences, no idioms) and use
     GitHub alerts (`> [!IMPORTANT]` …) sparingly for lines that must not be
     skimmed past — rules in the playbook.
4. **Restructuring an existing README?** Move content, don't delete it: deep
   sections become `docs/*.md` files with links from the README. Never invent new
   claims while restructuring. Add a TOC only if the result still exceeds ~400 lines.
5. **Syncing after code changes (drift)?** Don't rewrite — diff first, then apply
   the drift map in `references/readme-playbook.md` (dependency → Installation,
   env var → Configuration, endpoint/command → Usage, feature → Features;
   removed → prune, deprecated → mark with the replacement). The map names the
   primary sections — after applying it, search the whole README for the old
   identifiers and prune every hit. Preserve the README's existing tone and
   structure. Verify commands **safely**: static checks (files/flags/scripts
   referenced actually exist) and non-destructive local dry-runs only — never
   execute anything mutating, networked, or secret-requiring; list what was
   left unverified.
6. **Lint.** Run and fix everything it reports:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/readme_lint.py" README.md
   ```
7. **Show the result** with a one-paragraph rationale of the ordering choices.

## Output spec

A README.md where: exactly one H1; a one-sentence value prop directly under it;
≤5 badges; a working quick start in the first screen; task-based `##` headings
(GitHub builds the sidebar outline from them); every relative link resolves; no
hype words ("blazing", "revolutionary", "game-changing"); no placeholder left
unmarked. `scripts/readme_lint.py` exits 0.

## Gotchas

- **New/empty repo**: derive the one-liner from the user's idea and add **no**
  badges for CI/registries that don't exist yet. Placeholder policy: unknowns use
  `<angle-bracket-placeholders>`, are allowed **only** in this not-yet-built case,
  and must be listed in your summary — the linter warns on any left outside code
  blocks, and a published README must have none.
- GitHub truncates rendered READMEs above 500 KiB and auto-generates the heading
  outline — heading quality matters more than a hand-rolled TOC.
- A demo GIF beats paragraphs, but keep it under ~5 MB and only reference assets
  that are actually committed.
- Don't turn the README into a changelog or roadmap — link `CHANGELOG.md`/Releases.
- Write for a tired developer at 4 PM: second person, active voice, show don't tell.

## Files

- `references/readme-playbook.md` — section-by-section rules, length/tone guidance,
  anti-patterns, pre-publish checklist.
- `references/readme-templates.md` — copy-adapt skeletons (library, CLI, web app).
- `scripts/readme_lint.py` — deterministic structure checks; non-zero exit on errors.
