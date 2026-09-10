---
name: node-supply-chain
description: Hardens the npm supply chain - lockfile discipline, Dependabot cooldown and groups, per-package-manager install-script policy, provenance verification, npm token hygiene, SHA-pinned Actions. Use when the user asks to secure dependencies, audit npm packages, respond to a compromised dependency, or pin actions. Not for repo settings like rulesets/secret scanning, or publishing.
license: MIT
argument-hint: [harden|incident|dependabot]
---

# node-supply-chain

Layers the defenses that made the difference in real npm attacks — and names
what each layer does *not* cover. The failures this skill fixes: models
recommend `npm install` in CI, blanket auto-merge for bot PRs (a documented
malware path), treat cooldowns as full protection, and apply npm-specific
script policies to pnpm/yarn repos where they do nothing.

## When NOT to use

- GitHub repo settings (rulesets, secret scanning, PVR) → repo-settings
  tooling outside this collection (e.g. the github-skills `repo-protections`
  skill).
- Publishing your own package with provenance → `node-release`.
- Fixing a CVE in your own code → ordinary dev work.

## Workflow

1. **Baseline audit**:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/audit_supply_chain.py"
   ```
   Reports: lockfile state, CI install command, Dependabot config
   (cooldown/groups), unpinned third-party actions, install-script policy for
   the repo's actual package manager.
2. **Lockfile discipline**: committed lockfile; CI installs with
   `npm ci` / `pnpm install --frozen-lockfile` / yarn immutable — never bare
   install.
3. **Dependabot** (`.github/dependabot.yml`): npm + github-actions ecosystems,
   weekly, grouped, an explicit cooldown (github.com defaults to 3 days since
   2026-07-14; write the window you mean) — with its three real limits stated
   every time:
   security PRs bypass cooldown by design, transitive npm deps aren't covered,
   SHA-pinned actions don't alert. **Never blanket auto-merge bot PRs** — bot
   authorship has delivered malware on green CI; same review gate as humans.
4. **Install-script policy per package manager** (playbook table — npm >= 12
   `allowScripts` allowlist vs npm 11 `ignore-scripts`, pnpm `allowBuilds`, yarn
   `enableScripts`):
   apply the mechanism the repo's PM actually honors; allowlist the few packages
   that genuinely need build scripts.
5. **Provenance verification** (`npm audit signatures` — command version-gated
   in the playbook): treat as origin proof, never safety proof.
6. **Token hygiene**: no classic tokens; granular tokens with short lifetimes
   for what OIDC can't cover; account-level trusted-publishing-only enforcement
   (setup itself → `node-release`).
7. **Actions pinning**: third-party actions SHA-pinned with version comments;
   lint workflows with the checker from `node-ci` or zizmor.
8. **Incident response** (compromised upstream): the playbook checklist —
   determine exposure from the lockfile (exact resolved versions + install
   window), override/pin to known-good, document the window, then re-harden.

## Output spec

Audit script clean (or every finding dispositioned); Dependabot config with
cooldown+groups and no blanket auto-merge; per-PM script policy actually in
force; pinning applied; the three cooldown limits stated in the report — never
implied protection the config doesn't deliver.

## Gotchas

- npm/pnpm/yarn script policies are different mechanisms — an npm-only answer
  in a pnpm repo protects nothing.
- A cooldown is a bet someone else finds the malware inside the window — layer
  it, don't rely on it.
- `overrides`/`resolutions` fix exposure fast but rot silently — date-stamp
  them and remove after upstream ships clean.
- Version-gate npm CLI behaviors (script defaults, audit signatures) against
  npm's own docs at use time.

## Files

- `references/supply-chain-playbook.md` — layered model, per-PM script policy
  table, Dependabot config, provenance limits, token policy, incident checklist.
- `scripts/audit_supply_chain.py` — deterministic repo audit; non-zero exit on
  hard violations (no lockfile, bare install in CI, blanket bot auto-merge).
