# README Playbook — Writing a Professional Project README

Content and structure only: what to write, in what order, and how to phrase it.
Repo metadata (description, topics, social preview) and community-health files are
covered by sibling references — do not handle them here.

## Contents

- [The 10-second rule](#the-10-second-rule)
- [Canonical section order](#canonical-section-order)
- [The one-liner](#the-one-liner)
- [Badge discipline](#badge-discipline)
- [Demo: screenshot, GIF, or live link](#demo-screenshot-gif-or-live-link)
- [Installation and first-success usage](#installation-and-first-success-usage)
- [Length and navigation](#length-and-navigation)
- [Tone rules](#tone-rules)
- [Emphasis by project type](#emphasis-by-project-type)
- [Keep it true: the drift map](#keep-it-true-the-drift-map)
- [Anti-patterns](#anti-patterns)
- [Skeleton template](#skeleton-template)
- [Pre-publish checklist](#pre-publish-checklist)

## The 10-second rule

Treat the README as a landing page, not a document. Within ~10 seconds of landing,
a skimming visitor must be able to answer:

1. **What is this?** (one sentence)
2. **Why should I care?** (the benefit / why it beats alternatives)
3. **How do I try it?** (copy-paste commands)

Front-load ruthlessly: put all three above the fold — title, one-liner, badges,
one visual, and the first install command before any philosophy, architecture,
or feature catalog. Put proof before the catalog: a working example or screenshot
first, the full feature list after. Everything else can scroll.

Test it: read only the repo name, tagline, and first paragraph. If a stranger
cannot answer "what / for whom / what outcome / what next", rewrite the top.

## Canonical section order

Order sections by the visitor's journey. Each block has one job; do not let a
section do another block's job.

| # | Block | Sections | The block's job |
|---|-------|----------|-----------------|
| 1 | **Identity** | Title (H1), one-liner, badges | Say what it is and for whom in one glance. H1 = project name, nothing else. |
| 2 | **Proof** | Screenshot / GIF / live demo link | Show it working before asking the reader to do anything. |
| 3 | **Activation** | Installation, Quick start / Usage | Get the reader from zero to "it works" — copy-paste commands, smallest successful example, expected result. |
| 4 | **Expansion** | Features, Examples, Configuration, API overview | Answer "what else can it do?" with short bullets and 2–3 examples from simple to advanced. Link out for depth. |
| 5 | **Participation** | Contributing, Support | One short paragraph each; link to `CONTRIBUTING.md` and Discussions/support rather than inlining process detail. |
| 6 | **Governance** | License, Changelog link, Roadmap (optional), Status | State the license briefly (full text lives in `LICENSE`). Link to `CHANGELOG.md`/Releases. Be honest about maintenance status. |

Rules for the order:

- Never place governance or participation content above activation.
- Small projects may stop after Expansion — omit sections rather than pad them.
- Add a short **"Why it exists"** paragraph (2–3 lines: the problem, plus one
  design tradeoff you would defend) between Proof and Activation or right after
  the one-liner. It signals product judgment; keep it under 4 lines.
- If the project's status is beta, experimental, or unmaintained, say so
  explicitly in a Status line — surprising a contributor later erodes trust.

## The one-liner

Write the tagline before anything else. Formula:

> **ProjectName** is a **[category: tool/library/CLI/app]** for **[audience]**
> to **[outcome]** without **[pain point]**.

Rules:

- ≤ 10–25 words, one sentence, directly under the H1 (a `>` blockquote works well).
- Name the category in plain words ("framework", "command-line tool", "invoice
  generator") — humans and search systems both key on it.
- Concrete beats abstract: "Block risky AI-generated pull requests before they
  reach main" beats "An extensible platform for modern workflows".
- Positioning against a known tool is legitimate ("open-source X alternative
  with Y") when accurate.
- Do not start with "This is a..." or "A simple..." — lead with the capability.
- No marketing adjectives (see [Tone rules](#tone-rules)).

Follow with a pitch paragraph of **max three sentences** (what it is, who it's
for, why it's different). This intro block — title through pitch — should total
roughly **50–120 words**.

## Badge discipline

Badges are trust signals, not decoration. Use **3–5**, in one row, directly
under the title:

| Badge | Signal | Source |
|-------|--------|--------|
| CI / build status | "Tests pass, project is maintained" | GitHub Actions workflow badge (`.../actions/workflows/ci.yml/badge.svg`) |
| Package version | "Released and installable" | Registry badge (npm, PyPI, crates.io) via shields.io |
| License | "You can legally use this" | Static shields.io badge, e.g. `img.shields.io/badge/license-MIT-green` |
| Coverage *(optional)* | "Tested seriously" | Coverage service badge |
| Downloads *(optional)* | Adoption proof | Registry badge |

Rules:

- Every badge must link to or reflect live data, except the license badge, which
  is fine as a static shield.
- Delete anything decorative: "made with ❤️", "PRs welcome", tech-logo walls,
  visitor counters. A badge wall reads as amateur, not thorough.
- A broken or perpetually-red badge is worse than no badge — check them at
  release time.

## Demo: screenshot, GIF, or live link

Visual proof converts evaluation minutes into seconds. Place it above
Installation (apps) or above Usage (CLIs/libraries).

- **Web app / UI project:** one clean screenshot of the best screen, plus a live
  demo URL if one exists. A hosted demo is the single highest-value addition —
  it removes the install barrier entirely.
- **CLI:** an animated terminal capture (e.g. recorded with `vhs`) or a static
  capture of real command output.
- **Library / API:** a short code block with its expected output often beats an
  image; a diagram only if architecture is non-obvious (Mermaid renders natively
  on GitHub and diffs as text).
- **GIF rules:** ≤ ~10 seconds, high quality, and keep the file under **~5 MB** —
  large media makes the page crawl. GitHub Markdown cannot embed video, so a GIF
  or linked recording is the workaround.
- Give every image meaningful alt text; commit assets to the repo (e.g.
  `docs/assets/`) and use relative paths so forks and clones still render.
- Stale screenshots of a redesigned UI are worse than none — refresh them with
  releases.

## Installation and first-success usage

This section decides whether people actually try the project.

**Installation rules:**

- Copy-pasteable, complete, in a fenced `bash` block. **Never write "see the
  docs for installation"** — put the default install command right here and link
  out only for alternative platforms/package managers.
- State prerequisites explicitly (runtime version, required services) — never
  assume.
- If env vars are needed: ship `.env.example`, show `cp .env.example .env`, and
  list the required keys.
- Prefer the shortest safe path first; other install methods go one link away.
- **Verify with a fresh-clone loop:** clone into a clean directory (or container),
  follow the README verbatim, fix every gap, repeat until clone → running works
  in one uninterrupted pass. Commands must match the project's actual scripts
  (`package.json`, `Makefile`, etc.) exactly — setup drift kills trust faster
  than having no README.

**Usage rules:**

- Show the **smallest successful example**: one command or one self-contained
  code block a reader can copy into a new file and run unmodified.
- State the expected result in one line ("Opens `http://localhost:3000`",
  "Prints the parsed AST").
- Quick start should reach "it works" in **under 2 minutes and ≤ 5 steps**
  (ideally ~3 commands); if it takes more, simplify the setup, not the prose.
- Follow with 2–3 examples progressing simple → advanced; deeper recipes link
  out to `docs/` or examples folders.
- Name the section "Quick start" rather than "Installation" when both install
  and first run fit in one flow.

## Length and navigation

| Target | Guideline |
|--------|-----------|
| Intro block (title → pitch) | 50–120 words |
| Small project / utility | ~200–800 words total |
| Library / tool | ~500–1,500 words total |
| Longer than ~400 lines | Add an explicit table of contents or split content into `docs/` |
| Hard platform limit | GitHub truncates rendered READMEs above **500 KiB** — overstuffing silently hides content |

- GitHub **auto-generates an outline from headings** (the list icon on the
  rendered README), so heading quality *is* navigation quality: use task-based
  headings ("Installation", "Usage", "Configuration"), one H1 only, and a clean
  H2/H3 hierarchy. GitHub also auto-generates anchor IDs, so explicit TOC links
  are cheap to add.
- Treat the README as a landing page and table of contents: keep the minimum
  needed to evaluate, install, and start; move architecture essays, full config
  references, and API depth to `docs/`, a wiki, or a docs site, and link with
  descriptive anchor text ("API reference", not "click here").
- Word counts are targets for usefulness, not quotas — never pad with filler.

## Tone rules

- **Write for a tired developer at 4 PM.** Assume the reader is distracted and
  scanning, not studying. Short paragraphs, bullets, visual breaks.
- **Second person, active voice, imperative.** "Run `npm install`", not "The
  user should run…".
- **No hype words.** Delete "blazing fast", "revolutionary", "game-changing",
  "powerful", "seamless". If a claim matters, put evidence next to it — a
  benchmark link, badge, or example.
- **Show, don't tell.** A 3-line code example beats "it's easy to use". Demo
  before description, everywhere.
- **Benefit-phrased feature bullets**, 4–7 of them, each a single concrete
  sentence. "Zero configuration required" (benefit) beats "Supports
  configuration files" (capability); "Validates request bodies against JSON
  Schema with custom error messages" beats "Easy validation".
- **Write for a first-time visitor.** The curse of knowledge is the biggest
  README killer — spell out steps that feel obvious to you.
- **Write for a global audience.** Most GitHub readers are not native English
  speakers: short simple sentences (~9th-grade reading level), no idioms, no
  culture-specific references, one idea per sentence.
- **Use GitHub alerts for the few lines that must not be skimmed past** —
  sparingly (more than ~3 per README stops working):
  ```markdown
  > [!IMPORTANT]
  > Requires Node >= 22. Older versions fail at install time.

  > [!WARNING]
  > `--force` deletes untracked files.
  ```
  Available: `[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]` —
  rendered as colored callouts on github.com.
- Plain English, minimal jargon, honest scope. A short "known limitations" list
  reads as engineering maturity, not weakness.

## Emphasis by project type

Same skeleton, different weight:

| Project type | Lead with / expand | Keep minimal or skip |
|---|---|---|
| **Library / package** | Install one-liner, smallest code example with output, API surface overview (core entry points + link to full reference), 2–3 examples | Heavy visuals, roadmap prose, deployment notes |
| **CLI tool** | Terminal GIF/capture, install per platform (default first), `--help` output, a commands table, exit codes, config file/env vars | Web-style screenshots, long conceptual intros |
| **Web app** | Live demo link, hero screenshot, local setup with prerequisites + `.env.example`, run command with localhost URL, tech-stack list, deployment notes | Deep API reference inline (link out instead) |
| **Data science / research** | What question it answers, data requirements and provenance, environment/reproducibility setup (lockfile, seed), how to reproduce results, one result figure | Marketing framing; reproducibility *is* the pitch |

## Keep it true: the drift map

A README that lies is worse than a README that's thin — stale install steps and
phantom features are the fastest way to lose a reader's trust. When code changed
and the README didn't, sync it with this mapping instead of rewriting from
scratch:

| Code change | README section to update |
|---|---|
| New/changed dependency or supported runtime | Installation (+ prerequisites, engines) |
| New/renamed env var or config option | Configuration (and `.env.example` mention) |
| New/changed CLI command, API endpoint, or public function | Usage / Quick start / API overview |
| New user-facing feature | Features (benefit-phrased bullet) |
| Removed capability | Prune it everywhere — pruning beats appending |
| Deprecated (still works) capability | Mark it: replacement, planned removal version, one-line migration note |
| Changed defaults or breaking behavior | Quick start + a `[!IMPORTANT]` alert if it bites on upgrade |
| New badge-worthy signal (CI, coverage, release) | Badge row — and remove badges that died |

Sync rules:

- **Diff first**: read the actual change (git log/diff), start from the sections
  the map names — preserve the README's existing tone, structure, and
  formatting; a sync is not a rewrite.
- **The map is the starting point, not the boundary**: after the mapped
  sections, search the whole README (and its snippets, Docker examples, badges)
  for the old identifiers — renamed flags and env vars hide outside their home
  section.
- **Verify commands safely**: statically check that every referenced file,
  script, subcommand, and flag still exists; run only non-destructive local
  commands or `--dry-run`/`--help` forms. Never execute mutating, networked, or
  secret-requiring commands during a sync — list anything left unverified in
  your summary. Stale commands are drift even if no diff touched them.
- **Prune before you append.** Readers pay for every line; removed features and
  dead options go the same day. Deprecated-but-working features stay, marked
  with their replacement and removal timeline.
- Re-run the lint script after a sync — drift fixes often break relative links.

## Anti-patterns

Fix these on sight:

| Anti-pattern | Why it fails | Fix |
|---|---|---|
| **Badge wall** (10+ badges, tech logos, "made with ❤️") | Reads as decoration, buries the trust signals | Cut to 3–5 functional badges |
| **"AI slop" verbosity** — generic filler ("It's worth noting that…", "This ensures that…"), emoji-spam headers, bullets for everything, sections that restate each other | Flags the README as auto-generated and unreviewed; readers now treat over-polish as a *negative* signal | Cut filler, keep only sentences that inform an install/usage/evaluation decision; hand-verify every command |
| **Marketing prose before proof** | Visitors bounce before reaching the install command | Move demo + quick start above the pitch expansion |
| **Stale install steps** (commands that don't match the scripts, missing env vars, old package manager) | Erodes trust faster than no README at all | Fresh-clone loop before every release; update the README in the same PR as the change |
| **Changelog-in-README** (version history inline) | Bloats the page, drowns the landing content | Keep a `CHANGELOG.md` / Releases page and link to it |
| **"See the docs" for installation** | Adds friction at the exact moment of highest intent | Inline the default install + first example, always |
| **Wall of text, no TOC** over ~400 lines | Unscannable; readers can't find their section | Add a TOC or split into `docs/` |
| **Vague one-liner** ("A platform for modern workflows") | Fails the 10-second test | Rewrite with the one-liner formula |
| **Broken images / dead links / red badges** | Signals abandonment | Check all links and rendering at release time |
| **Unstated project status** | Contributors invest in an abandoned repo | Add an honest Status line |

Note on ROI claims: widely-circulated numbers ("polished READMEs get N× more
stars", "recruiters spend 7 seconds") are directional at best and unverified —
never cite them in a README or use them to justify padding. The structural
consensus (front-loading, quick start, visual proof) is what holds up.

## Skeleton template

Adapt, then delete unused sections — never ship placeholders.

````md
# ProjectName

> One-line: what it does, who it's for, the outcome it enables.

![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)
![Version](https://img.shields.io/badge/version-x.y.z-blue)
![License](https://img.shields.io/badge/license-MIT-green)

ProjectName helps [audience] [solve problem] with [key differentiator].
[Optional: one tradeoff/decision you'd defend.]

![Demo](docs/assets/demo.gif)

## Quick start

```bash
<install command>
<run command>
```

Expected result: <one line>.

## Features

- <benefit-phrased bullet> (4–7 total)

## Examples

- [Basic](examples/basic) · [Advanced](examples/advanced)

## Documentation

- [Getting started](docs/getting-started.md) · [API reference](docs/api.md)

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
````

## Pre-publish checklist

Run before merging any README:

- [ ] H1 matches the project/repo name; one-liner passes the 10-second test
- [ ] Intro block is 50–120 words with no hype words
- [ ] 3–5 functional badges, all rendering and green (license badge may be static)
- [ ] At least one visual (screenshot, GIF ≤ ~5 MB, or live demo link) above the fold
- [ ] Install commands verified via fresh-clone on a clean machine; prerequisites and env vars stated
- [ ] Quick start reaches a visible "it works" in ≤ 5 steps / ~2 minutes, with expected result stated
- [ ] Smallest-success usage example is self-contained and runnable as pasted
- [ ] Feature bullets are benefit-phrased, concrete, 4–7 items
- [ ] Depth (full config, API detail, architecture) linked out, not inlined; TOC present if over ~400 lines
- [ ] License stated; changelog linked (not inlined); project status honest
- [ ] No broken links or images; headings form a clean outline (GitHub's auto-TOC reads them)
- [ ] Read once as a first-time visitor: nothing assumes knowledge only the author has
