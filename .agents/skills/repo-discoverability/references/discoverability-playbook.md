# Repo Discoverability Playbook

How a GitHub repository gets found: the metadata levers you control, how GitHub
search uses them, and how to measure whether changes worked. This file is about
**metadata and search behavior only** — README prose and section writing are
covered elsewhere.

## Contents

- [The two-tier model](#the-two-tier-model)
- [Tier 1: GitHub-native levers](#tier-1-github-native-levers)
  - [Repository name and H1 alignment](#repository-name-and-h1-alignment)
  - [Repository description](#repository-description)
  - [Topics](#topics)
  - [Homepage URL](#homepage-url)
  - [Social preview image](#social-preview-image)
  - [Headings and the auto-generated outline](#headings-and-the-auto-generated-outline)
  - [Descriptive anchor text](#descriptive-anchor-text)
  - [Freshness](#freshness)
- [How GitHub search matches repos](#how-github-search-matches-repos)
- [Tier 2: web-search levers](#tier-2-web-search-levers)
- [Prioritized effort/return table](#prioritized-effortreturn-table)
- [gh CLI command reference](#gh-cli-command-reference)
- [Measurement](#measurement)
- [Claims to never make](#claims-to-never-make)
- [Pre-ship checklist](#pre-ship-checklist)

## The two-tier model

Repo "SEO" operates on two layers. Do not conflate them: a README cannot set
HTML `<head>` metadata for the repository page — GitHub controls that page.

| Layer | What you control | Levers |
|---|---|---|
| **GitHub-native discovery** (GitHub search, topic pages, Explore, social unfurls) | Repo metadata, not full HTML | Repo name, one-line description, topics, homepage URL, README H1 + headings, social preview image |
| **Web/AI discovery** (Google, LLM crawlers) | Full page metadata — but only on a site you own | Docs site or GitHub Pages: `<title>`, meta description, `WebSite` structured data, readable URLs |

Work Tier 1 first — every lever is a one-line `gh` command or a settings toggle.
Tier 2 requires a docs/Pages site and only pays off for projects that warrant one.

## Tier 1: GitHub-native levers

### Repository name and H1 alignment

- Use a short, memorable, lowercase-hyphenated repo name.
- Make the README H1 match the repo name (or product name) exactly. One clear
  H1 — multiple equally prominent headings confuse title generation for search
  systems and humans alike.
- If the name is cryptic for historical reasons, do NOT rename (renames break
  links and muscle memory); compensate with a plain-language description and H1
  subtitle instead.

### Repository description

The description is the repo's **About text, its GitHub search snippet, and the
default text in social unfurls** — the single highest-leverage sentence you
control. Write it with this formula:

```
[Category keyword] for [audience] to [outcome].
```

Rules:

- Lead with plain **category words** people actually type: "CLI", "framework",
  "library", "template", "web app", "data apps", "APIs". Successful large
  projects all do this ("GitHub on the command line", "The React Framework").
- Name the audience and the outcome, not features.
- Keep it to one sentence, ideally under ~120 characters so it displays without
  truncation in search results and unfurls.
- No emoji walls, no "blazing fast", no trailing marketing clause.

```bash
gh repo edit OWNER/REPO --description "CLI for release managers to generate changelogs from conventional commits"
```

### Topics

Topics feed GitHub search, the browsable `github.com/topics/<topic>` pages, and
Explore. GitHub allows up to 20 topics per repository; topics must be lowercase,
start with a letter or number, and may contain hyphens.

Set **5–10 accurate topics**, one or two from each bucket:

| Bucket | Examples |
|---|---|
| Category | `cli`, `framework`, `library`, `template`, `devtools` |
| Language/runtime | `python`, `typescript`, `rust`, `nodejs` |
| Use case | `code-review`, `changelog`, `data-visualization` |
| Domain/ecosystem | `github-actions`, `kubernetes`, `llm`, `claude` |

Prefer topics that already have populated topic pages (check
`github.com/topics/<topic>`) — an invented topic no one browses helps nobody.
Accurate beats exhaustive: never add a popular topic the repo doesn't genuinely
belong to.

```bash
gh repo edit OWNER/REPO --add-topic cli,changelog,developer-tools,python
gh repo edit OWNER/REPO --remove-topic wrong-topic
gh api repos/OWNER/REPO/topics --jq '.names'   # verify
```

### Homepage URL

Set the homepage to the docs site, live demo, or package page. It renders in
the About sidebar next to the description and gives searchers a one-click path
past the repo.

```bash
gh repo edit OWNER/REPO --homepage "https://example.github.io/repo/"
```

### Social preview image

Until you upload one, links shared to Slack/X/LinkedIn/Discord unfurl as the
bare repo name plus owner avatar — an easy-to-miss lever. With one, every share
becomes a branded card.

- Make a **simple branded image**: project name + one-line value promise, or a
  clean product screenshot. No dense text.
- GitHub's documented specs: at least 640×320 px, **1280×640 px for best
  display**, PNG/JPG/GIF under 1 MB.
- Upload location: **Settings → General → Social preview** (web UI only — there
  is no API/CLI to set it).
- Verify from the CLI:

```bash
gh repo view OWNER/REPO --json openGraphImageUrl,usesCustomOpenGraphImage
```

`usesCustomOpenGraphImage: false` means the repo is still shipping the default
auto-generated card.

### Headings and the auto-generated outline

GitHub auto-builds the README outline (the TOC menu on the rendered page)
directly from Markdown headings — heading quality IS navigation quality.

- Use **task-based headings**: "Installation", "Usage", "Configuration",
  "Examples", "Contributing" — not "Getting going" or "The good stuff".
  They are scannable for humans and explicit for search systems.
- Keep one H1; start sections at H2.
- GitHub truncates rendered README content beyond **500 KiB** — anything past
  that never renders, never appears in the outline. Keep the README lean and
  link out.

### Descriptive anchor text

Links help crawlers discover pages and understand relevance; anchor text is the
signal. Always name the destination: "API reference", "installation guide",
"live demo". Never "click here", "this link", or a bare "here".

### Freshness

Directional, unverified as a precise ranking factor — but grounded in
documented behavior: GitHub search offers "recently updated" sorting, and
Explore/trending surfaces favor active repos. A repo pushed once and abandoned
loses those surfaces entirely. Practical rule: ship real commits regularly
rather than batching a year of work into one push, and never fake activity for
its own sake.

**People-first warning**: do not keyword-stuff the description, topics, or
headings. Search systems explicitly prioritize content written to help people
over content written to manipulate rankings; concrete category words placed
once beat repeated keywords every time. Stuffing also reads as spam to the
humans deciding whether to click.

## How GitHub search matches repos

- Repository search matches primarily on **name and description**; qualifiers
  let searchers target `in:name`, `in:description`, `in:topics`, and
  `in:readme` explicitly.
- `topic:<name>` filters to repos tagged with that exact topic — one more
  reason topics must be accurate, not aspirational.
- Consequence: the README body is weak search surface on GitHub itself; the
  name, description, and topics carry the match. Spend your keyword thinking
  there.

Test your own discoverability the way a stranger would:

```bash
gh search repos "changelog generator" --limit 10
gh search repos --topic changelog --sort stars --limit 10
```

If the repo doesn't appear for the phrases its audience would type, fix the
description and topics first.

## Tier 2: web-search levers

Only available once the project has a docs site or GitHub Pages site — that is
where real `<head>` control lives.

- **Title tag**: one clear, distinctive title per page; the home page title
  should match the project name.
- **Meta description**: hand-write one per key page; search snippets draw from
  page content and meta descriptions.
- **Structured data**: add `WebSite` structured data on the docs home page so
  the site name is understood.
- **Readable URLs**: human words with hyphens (`/docs/getting-started`), not
  IDs or query strings.
- Link the docs site from the repo homepage field and README so crawlers find
  it; link back to the repo from the docs site.

Note: even fully compliant pages are not guaranteed indexing or ranking — treat
all of this as improving the odds, not buying placement.

## Prioritized effort/return table

Effort/return ratings are reasoned estimates from platform mechanics, not
guaranteed ranking impact. Do the Low/High rows in a single sitting.

| Lever | Effort | Return |
|---|---:|---:|
| One-line description with category keywords | Low | High |
| Accurate topics (5–10) | Low | High |
| Repo name ↔ README H1 alignment | Low | High |
| Task-based headings (feeds auto-outline) | Low | High |
| Homepage URL set | Low | Medium |
| Descriptive anchor text | Low | Medium |
| Social preview image | Medium | Medium–High |
| Docs/Pages title + meta description | Medium | High |
| Structured data on docs home page | Medium–High | Medium–High |
| Readable docs URLs | Medium | Medium |

## gh CLI command reference

Every Tier 1 lever except the social preview image is scriptable:

```bash
# Set the About metadata
gh repo edit OWNER/REPO --description "Category for audience to outcome"
gh repo edit OWNER/REPO --homepage "https://docs.example.com"

# Topics (comma-separated; repeatable)
gh repo edit OWNER/REPO --add-topic cli,changelog,python
gh repo edit OWNER/REPO --remove-topic stale-topic

# Audit current state
gh repo view OWNER/REPO --json name,description,homepageUrl,repositoryTopics
gh repo view OWNER/REPO --json openGraphImageUrl,usesCustomOpenGraphImage
gh api repos/OWNER/REPO/topics --jq '.names'

# See the repo as searchers do
gh search repos "your key phrase" --limit 10
```

Social preview upload remains manual: Settings → General → Social preview.

## Measurement

GitHub's traffic data covers a **rolling 14-day window** and requires push
access. Snapshot before a metadata change, again 14 days after, and control for
launches/posts in between. For longer analysis, export snapshots periodically —
the window does not extend backwards.

```bash
gh api repos/OWNER/REPO/traffic/views              # daily views + uniques, 14 days
gh api repos/OWNER/REPO/traffic/clones             # daily clones + uniques, 14 days
gh api repos/OWNER/REPO/traffic/popular/referrers  # top referring sites
gh api repos/OWNER/REPO/traffic/popular/paths      # top content within the repo
```

What each metric means for discoverability work:

| Signal | Interpretation | Action |
|---|---|---|
| Views/uniques rise | Discovery levers (description, topics, sharing, social preview) are working | Keep going; check conversion next |
| Views rise, clones flat | People find it but don't evaluate it | Content problem, not a discoverability problem — hand off to README/quickstart work |
| Clones rise | Serious evaluation or adoption | Discoverability + content both working |
| Referring sites | Which channels actually deliver visitors | Invest where traffic originates; a docs site appearing here means Tier 2 works |
| Popular content shifts README → docs pages | README acting as gateway, docs carrying depth | Healthy; leave it |
| Stars rise, other metrics flat | Top-of-funnel social proof only | Fine, but don't optimize for it directly |

Caveat: any vendor claim converting these metrics into multipliers ("X% more
stars from doing Y") is directional at best — see below.

## Claims to never make

These widely-circulated statistics failed independent verification and trace to
vendor blogs. Never state them as fact in a README, pitch, or commit message:

- "Comprehensive READMEs get **2.5x more stars / 3x more contributions**" — unverified.
- "Polished READMEs get **4x more stars and 6x more contributors**" — no credible primary source.
- "Recruiters spend **~7 seconds** scanning a README" — unverified.
- Any fixed "star conversion %" from adding a badge or chart — unverified.

If you need a hedge, say "directional, unverified" or cite nothing.

## Pre-ship checklist

- [ ] Description follows `[category] for [audience] to [outcome]`, ≤ ~120 chars
- [ ] 5–10 accurate topics spanning category / language / use case / domain
- [ ] Repo name matches README H1
- [ ] Homepage URL points to docs, demo, or package page
- [ ] Custom social preview uploaded (1280×640 px) — `usesCustomOpenGraphImage: true`
- [ ] Headings are task-based; outline menu reads like a TOC
- [ ] All link text names its destination (no "click here")
- [ ] `gh search repos "<audience phrase>"` surfaces the repo, or you know why not
- [ ] Traffic snapshot taken (views, clones, referrers) to compare in 14 days
- [ ] If a docs/Pages site exists: title, meta description, structured data, clean URLs
