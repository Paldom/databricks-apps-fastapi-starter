# Required checks, rulesets, and merge queues

**Contents:** [Why matrix legs make bad required checks](#why-matrix-legs-make-bad-required-checks) ·
[Aggregator options](#aggregator-options-and-trade-offs) ·
[Rulesets vs classic branch protection](#rulesets-vs-classic-branch-protection) ·
[gh api recipes](#gh-api-recipes) · [Merge queues](#merge-queues) ·
[Tag rulesets](#tag-rulesets) ·
[Diagnostic playbook: green PR won't merge](#diagnostic-playbook-green-pr-wont-merge) ·
[Sources](#sources)

## Why matrix legs make bad required checks

GitHub binds a required status check to a **static context name** like
`test (3.11)`. Three ways this breaks:

1. **Matrix change**: add `3.14` or drop `3.10` and the old context names vanish.
   The rule still expects them → every PR stalls on "waiting for status to be
   reported". Nothing in the UI tells you why.
2. **Job rename**: same failure, one job at a time.
3. **Skipped counts as success**: a required job skipped by a path filter or a
   misconfigured `if:` satisfies the rule *without running anything* — GitHub
   treats required checks as met when they are "successful", "skipped", or
   "neutral". "Skippable checks aren't really required."

Also: duplicate job names across different workflow files make the context
ambiguous and can block merges even when everything passed. Keep job names unique
repo-wide.

## Aggregator options and trade-offs

Recommended near-identically by several independent sources; pick one:

**Option A — `all-checks-passed` (recommended default).** One trailing job with
`needs:` on everything and `if: always()`, failing when any needed result is
`failure`/`cancelled` (add `skipped` when nothing is intentionally skippable).
Only this job is marked required. Pro: one stable name forever; matrix shape and
repo settings fully decoupled. Con: adds a few seconds of critical path; the
`if: always()` line is load-bearing and non-obvious — comment it.

**Option B — failure-alert job.** A job that is *skipped unless something went
wrong*: `if: cancelled() || contains(needs.*.result, 'failure') ||
contains(needs.*.result, 'cancelled')`, whose only step is `exit 1`. Because
skipped counts as success, the check passes when it never runs. Pro: zero added
critical path. Con: deliberately relies on the skipped=success quirk — document
it heavily or the next maintainer "fixes" it.

**Option C — require every leg.** Works only for a frozen matrix; every matrix
edit requires a settings edit someone will forget. Treat as inherently unsafe;
listed only so you can recognize and replace it.

For path-filtered pipelines, Option A's aggregator should read the filter
outputs and pass when nothing relevant changed (worked example in
[ci-workflow-template.md](ci-workflow-template.md)).

## Rulesets vs classic branch protection

| | Classic branch protection | Rulesets |
| --- | --- | --- |
| Rules per branch | one rule applies | multiple layer; most restrictive wins |
| Targets | branches only | branches **and tags** |
| Governance | per-repo | org-level inheritance possible |
| Rollout | immediate | "Evaluate" preview mode |
| Bypass | coarse admin toggle | fine-grained bypass actors (apps, roles) |
| Admins bound by default | no — must enable enforce_admins | bypass list is opt-in |
| Extras | — | path-conditional required checks |
| IaC/Terraform support | mature | still catching up (hybrids are common) |

GitHub is steering users toward rulesets. Migrate when you need tag protection,
org-level consistency, or bot bypasses without granting admin; classic is fine
for one simple repo. Either way: the setting that matters most is **no bypass for
admins** — an agent or attacker with an admin token merges past every check
otherwise.

## gh api recipes

Classic protection (idempotent PUT — note the API requires all four fields):

```bash
# --field sends strings; nested objects need a JSON body (--input).
gh api repos/{owner}/{repo}/branches/main/protection --method PUT --input - <<'JSON'
{ "required_status_checks": { "strict": true, "contexts": ["all-checks-passed"] },
  "enforce_admins": true,
  "required_pull_request_reviews": { "required_approving_review_count": 1, "dismiss_stale_reviews": true },
  "restrictions": null }
JSON
```

Ruleset (branch, required check + PR review + no force push):

```bash
gh api repos/{owner}/{repo}/rulesets --method POST --input - <<'JSON'
{
  "name": "main-quality-gate",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request",
      "parameters": { "required_approving_review_count": 1,
                      "dismiss_stale_reviews_on_push": true,
                      "require_code_owner_review": false,
                      "require_last_push_approval": false,
                      "required_review_thread_resolution": false } },
    { "type": "required_status_checks",
      "parameters": { "strict_required_status_checks_policy": false,
                      "required_status_checks": [ { "context": "all-checks-passed" } ] } }
  ]
}
JSON
```

Verify with `gh api repos/{owner}/{repo}/rulesets` and by opening a test PR.
Field names occasionally evolve — on a 422, compare against
https://docs.github.com/en/rest/repos/rules.

Chicken-and-egg: a check context is only selectable (and only *satisfiable*)
after it has reported at least once — run the workflow on a branch/PR before
wiring the rule. You can type the exact context name manually, but a typo'd or
never-reporting context blocks everything.

## Merge queues

Merge queues re-validate PRs against a speculative merge with current `main`,
closing the "two individually green PRs break main" gap, and remove the
`strict: true` rebase treadmill.

- The workflow backing required checks **must** trigger on `merge_group` —
  without it, queue validation silently never reports and PRs sit "waiting for
  status checks" despite green PR runs. This is the single most common
  merge-queue failure.
- Pattern: light checks on `pull_request`, heavier validation on `merge_group`
  (`if: github.event_name == 'merge_group'` on the expensive jobs), required
  checks satisfied at queue stage.
- The queue is itself a moving part: stuck queues and silent failures are
  reported in the wild — if PRs pile up, check the queue's own status before
  debugging workflows.
- Concurrency groups keyed on `github.ref` are queue-safe; do not
  `cancel-in-progress` merge_group runs.

## Tag rulesets

Rulesets can target tags — block deletion, non-fast-forward updates, and restrict
who can create tags matching `v*`. For a repo that publishes from tags, a tag
ruleset prevents re-tagging an existing release at a different commit (a real
attack pattern against action/tag consumers). Creating the release automation
itself is python-release territory; the protection rule belongs to this gate.

## Diagnostic playbook: green PR won't merge

Work top to bottom; each step is a distinct documented failure:

1. `gh pr checks <n>` — which required context is missing (not failing, missing)?
2. Does that context name still exist as a job name in any workflow? Rename or
   matrix change → update the rule (or switch to the aggregator, permanently).
3. Did the workflow trigger at all? Path filters / `paths-ignore` mean a
   docs-only PR never produces the check → aggregator with filter-aware pass.
4. Merge queue on? Confirm `merge_group` is in the workflow triggers.
5. Duplicate job names across workflows → make them unique.
6. Check ran on a different commit SHA than the PR head (e.g. after a force
   push) → re-run on the head commit.
7. "Required review from code owners" + stale approvals: a new push dismissed
   the approval (`dismiss_stale_reviews`) — re-request review, don't disable
   dismissal.
8. You're an admin and still blocked → `enforce_admins`/no-bypass is on. That is
   working as intended; fix the check, don't bypass the rule.

## Sources

- Troubleshooting required status checks (merge_group note, skipped semantics):
  https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks
- About protected branches:
  https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- About rulesets:
  https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
- Branch protection REST API: https://docs.github.com/en/rest/branches/branch-protection
- Required-checks quirks with conditional/matrix jobs (Options A/B/C worked
  examples):
  https://devopsdirective.com/posts/2025/08/github-actions-required-checks-for-conditional-jobs/
- Dynamic status checks and the aggregator pattern:
  https://matthewbusche.com/2026/02/27/github-actions-dynamic-status-checks/
- "Why can't I select my check" (community discussion):
  https://github.com/orgs/community/discussions/167194
