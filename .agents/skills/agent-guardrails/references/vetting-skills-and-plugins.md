# Vetting and installing public skills, plugins, and MCP servers

Contents: [Threat model](#threat-model) · [Vetting checklist](#vetting-checklist) ·
[Curated starting points](#curated-starting-points) · [Team distribution](#team-distribution) ·
[Committed-hook security](#committed-hook-security) · [Sources](#sources)

## Threat model

Plugins, skills, and MCP servers execute with the developer's full local
permissions — Anthropic's docs say plainly that plugins "can execute arbitrary
code on your machine with your privileges," and third-party marketplaces are
not verified. Real incidents exist across the surface: a marketplace plugin
that funneled repo-local rule files into the trusted prompt channel (prompt
injection + secret exfiltration), scans finding a meaningful share of
uncurated marketplace skills with risky patterns (hardcoded secrets,
exfiltration instructions — reported rates vary by scan and are
vendor-published; treat the direction, not the numbers, as the finding), and
MCP tool descriptions/error responses used as injection vectors. Treat every
install as adding an unreviewed dependency with shell access.

## Vetting checklist

Before installing anything third-party:

1. **Manifest** — read `plugin.json`; an `mcpServers` entry means external
   network connections.
2. **Hooks** — inspect any `hooks/` directory: which events, what commands.
   A hook you didn't read is code execution you didn't review.
3. **Skill bodies** — read each full SKILL.md (not just the description):
   look for `curl | bash`, safety disables, instructions to send data out,
   and unpinned `uvx`/`npx` execution (a skill running an unpinned tool
   executes whatever was published last).
4. **Permission proportionality** — a commit-message formatter has no
   business requesting broad filesystem or network access.
5. **Pin and review updates** — pin plugin versions; review updates like
   dependency bumps. Auto-updating an agent plugin is `curl | bash` on a
   schedule.
6. For scale, scanners exist (e.g. Cisco's open-source skill-scanner:
   static signatures + bytecode + LLM prompt-injection analysis) — useful
   triage, not a substitute for reading.

## Curated starting points

Vetted-by-reputation, still read-before-install:

- **Astral official skills** for uv/ruff/ty — fixes the bare-pip failure mode
  natively; from the toolchain vendor.
- **proven-python** (github.com/shanwije/proven-python, MIT) — quality gate
  skill: failing-test-first, strict typing, nothing "done" until
  ruff+mypy+pytest are green; ships pyproject/pre-commit/CI templates. Its
  design rule is worth stealing: "a command that fails the build beats a
  paragraph asking the model to behave."
- **trailofbits/skills** and **trailofbits/claude-code-config** —
  security-focused skills and an opinionated blocking-defaults config; their
  Modern Python setup shims bare `python`/`pip` on PATH to print the uv
  equivalent and exit non-zero.
- **Anthropic's official plugin directory** (anthropics/claude-plugins-official)
  — automated screening plus a stricter human-review tier; listed ≠ audited,
  the checklist above still applies.

## Team distribution

- Project scope: commit `extraKnownMarketplaces` and `enabledPlugins` in
  `.claude/settings.json` — contributors are prompted on folder trust.
- Personal experiments: `.claude/settings.local.json` (gitignored).
- Enterprise lockdown: `strictKnownMarketplaces` restricts allowed sources.
- Removing a marketplace uninstalls everything installed from it — surprising
  blast radius; plan before consolidating.

## Committed-hook security

`.claude/settings.json` ships with the repo: every contributor who clones and
runs the agent inherits its hooks — including malicious ones from a
compromised PR. There has been at least one real CVE where repo files
triggered code execution before the trust dialog was even accepted
(CVE-2025-59536, patched). Consequences:

- Put `.claude/**` behind CODEOWNERS and require code-owner review.
- Review diffs to `.claude/**` in the web UI *before* checking out a PR
  branch and starting an agent session in it.
- Never feed repo-local files into a hook's trusted output channel without
  sanitization (the marketplace-plugin injection pattern).
- Whitelist utilities in command-inspecting hooks rather than blacklisting
  patterns.

## Sources

- Plugin security model — https://code.claude.com/docs/en/plugins
- Official directory — https://github.com/anthropics/claude-plugins-official
- Skill-distribution risks — https://blog.trailofbits.com/2026/06/03/
- Cisco skill scanner — https://github.com/cisco-ai-defense/skill-scanner
- proven-python — https://github.com/shanwije/proven-python
- Trail of Bits skills — https://github.com/trailofbits/skills
