# Claude Code hooks — mechanics reference

Contents: [Events](#events) · [Exit codes per event](#exit-codes-per-event) ·
[settings.json shape](#settingsjson-shape) · [Matchers](#matchers) ·
[The if field](#the-if-field) · [JSON output](#json-output) ·
[Timeouts](#timeouts) · [Scopes and merging](#scopes-and-merging) ·
[Coverage gaps](#coverage-gaps) · [Known issues and version drift](#known-issues-and-version-drift) ·
[Debugging checklist](#debugging-checklist) · [Sources](#sources)

Verified against https://code.claude.com/docs/en/hooks on 2026-09-10. The surface
still moves between releases — when this file and the docs disagree, the docs win.

## Events

The docs enumerate 33 lifecycle events (as of Claude Code 2.1.26x). The ones this skill builds on:

| Event | Fires | Use here |
| --- | --- | --- |
| `PreToolUse` | before a tool call (matcher = tool name) | deny never-do commands; the only *prevention* point |
| `PostToolUse` | after a tool call **succeeds** | single-file feedback on the edit that just landed |
| `PostToolUseFailure` | after a tool call fails | stderr shown in the transcript; not needed for the gates here |
| `Stop` / `SubagentStop` | the agent wants to end its turn | run the commit gate; refuse while red |
| `ConfigChange` | a settings file changes mid-session (matchers `user_settings`, `project_settings`, `local_settings`, `policy_settings`, `skills`) | block an agent editing its own guardrails (`project_settings`); `policy_settings` cannot be blocked |
| `FileChanged` | a watched path changes on disk | catch `sed -i`/heredoc writes that never pass through `Edit` |
| `UserPromptSubmit` | before a prompt is processed | context injection or prompt blocking (rarely needed for repo gates) |
| `SessionStart` (`startup`/`resume`/`clear`/`compact`/`fork`) / `SessionEnd` | session lifecycle | context injection / cleanup; not blockable |

Others (`Setup`, `UserPromptExpansion`, `PermissionRequest`, `PermissionDenied`,
`PostToolBatch`, `Notification`, `MessageDisplay`, `SubagentStart`, `TaskCreated`,
`TaskCompleted`, `StopFailure`, `TeammateIdle`, `InstructionsLoaded`, `CwdChanged`,
`DirectoryAdded`, `WorktreeCreate`/`WorktreeRemove`, `PreCompact`/`PostCompact`,
`PreModelSwitch`/`PostModelSwitch`, `Elicitation`/`ElicitationResult`) exist; the
docs' per-event table is the source of truth for what each can block.

## Exit codes per event

The contract: `exit 0` proceed · `exit 2` block (on blockable events) · **any other
code with plain-text output = non-blocking, logged, action proceeds** (the exit-1
footgun). Two facts everyone gets wrong:

- **Stdout JSON is read on every exit code**, not only on 0. Valid decision JSON on
  exit 1 is honored; on exit 2 the block cannot be overridden (a `permissionDecision:
  "allow"` is ignored) but the JSON's `reason` becomes the message shown.
- **The block reason on exit 2 is the JSON decision's reason if present, otherwise
  stderr.** Plain text on stdout is neither — it is dropped.

| Event | What exit 2 does | Notes |
| --- | --- | --- |
| `PreToolUse` | prevents the tool call | fires even under skip-permissions modes — hooks tighten, never loosen |
| `PostToolUse` / `PostToolUseFailure` | nothing to prevent — the tool already ran | stderr becomes corrective feedback to the agent; reaction, never prevention |
| `Stop` / `SubagentStop` / `TeammateIdle` | prevents *stopping* — forces continued work | MUST guard on `stop_hook_active` in the stdin JSON; the harness overrides after 8 consecutive blocks without progress (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`) |
| `UserPromptSubmit` / `UserPromptExpansion` | blocks the prompt (and erases it) | stdout on exit 0 is injected into context |
| `ConfigChange` / `WorktreeCreate` / `TaskCreated` / `TaskCompleted` | blocks the change | `policy_settings` changes cannot be blocked |
| `PostToolBatch` | halts the agent loop before the next model request | |
| `PermissionRequest` | **not honored** — decide through the JSON `decision` object | |
| `SessionStart` / `SessionEnd` / `Notification` | not blockable | context injection / cleanup only |

Blockable events, per the docs: `PreToolUse`, `UserPromptSubmit`, `UserPromptExpansion`,
`Stop`, `SubagentStop`, `TeammateIdle`, `TaskCreated`, `TaskCompleted`, `ConfigChange`,
`WorktreeCreate`. `PostToolUse` is **not** one of them.

## settings.json shape

Three levels of nesting; getting this wrong fails silently:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/lint_edited_file.py\"",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

- `$CLAUDE_PROJECT_DIR` is the project root where the session started — it stays
  put across `cd` and worktrees, which is why every script path uses it. Handlers
  themselves run in the *current* directory, so a script that needs the repo
  must `cd` to `$CLAUDE_PROJECT_DIR` (the shipped `stop_verify.py` does).
  Literal `$HOME` in the command string may not expand — another silent failure.
- Handler types beyond `command`: `http` (blocks only via a 2xx response carrying
  `decision:"block"` — 4xx/5xx/timeouts degrade to non-blocking), `prompt` and
  `agent` (model-judgment handlers), `mcp_tool`. For hard policy use `command`
  hooks only: anything that can time out or disconnect fails open.
- Hook input arrives as JSON on stdin (`tool_input.file_path` for file events,
  `tool_input.command` for Bash, `stop_hook_active` on Stop, `agent_id`/`agent_type`
  inside subagents). Read it with `json.load(sys.stdin)` — the shipped hooks are
  stdlib Python, so nothing depends on `jq`.

## Matchers

- Case-sensitive. `bash` and `edit` match nothing, silently.
- Letters, digits, `_`, `-`, spaces, commas and `|` → an exact tool name or a list
  (`Edit|Write`, `Edit, Write`). Any other character → an **unanchored** JavaScript
  regex: `Edit.*` also matches `NotebookEdit`; `mcp__memory` alone is exact and
  matches nothing — use `mcp__memory__.*`.
- Empty string, `*`, or omitted → matches every occurrence of the event.
- Per-event matcher targets differ: tool name for tool events (built-ins include
  `Bash`, `PowerShell`, `Edit`, `Write`, `NotebookEdit`, `Read`, `Glob`, `Grep`,
  `Agent`, `Workflow`, `WebFetch`, `WebSearch`, `AskUserQuestion`, `ExitPlanMode`,
  plus MCP tool names); source (`startup`/`resume`/`clear`/`compact`/`fork`) for
  `SessionStart`; settings scope for `ConfigChange`; trigger for `PreCompact`;
  notification type for `Notification`.
- Multiple matching hooks all run (in parallel); duplicates across settings files
  run once; for PreToolUse the most restrictive merged decision wins
  (deny > defer > ask > allow).

## The if field

`"if": "Bash(git *)"`-style filters (permission-rule syntax) narrow tool events
without editing the script. Two hard caveats: older versions silently ignore the
field (hook then runs on every match), and the docs call the filter
**best-effort — it fails open** on commands it cannot parse. Use the permission
system, not `if`, for anything that must hold.

## JSON output

The fine-grained alternative to exit codes, read on every exit code:

- Common fields: `continue: false` + `stopReason` (halt the agent),
  `systemMessage` (a warning shown to the user — the only way an exit-0 hook's
  message reaches the transcript), `suppressOutput` (no effect on transcripts).
- `PreToolUse`: `hookSpecificOutput.permissionDecision` of `allow`/`deny`/`ask`/
  `defer` (plus input-rewriting via `updatedInput`, `updatedPermissions`). Note
  `ask` is the middle ground exit codes cannot express — human sign-off.
- Other blockable events: top-level `{"decision": "block", "reason": "..."}`.
- `Stop`/`SubagentStop` can return `hookSpecificOutput.additionalContext` for
  soft steering without a hook-error label.
- JSON that fails schema validation on exit 2 still blocks; stderr becomes the
  reason and the validation failure lands in the debug log.

## Timeouts

Per-hook `"timeout"` is in seconds. Defaults: **600** for `command`/`http`/`mcp_tool`
(30 on `UserPromptSubmit` and model-switch events, 10 on `MessageDisplay`), 30 for
`prompt`, 60 for `agent`. A hook that hits its timeout is **non-blocking** — a
silent pass — so set an explicit value with headroom above the script's own inner
timeouts, keep PostToolUse work sub-second, and pre-build slow environments
(`pre-commit install --install-hooks`) at setup.

## Scopes and merging

| File | Scope | Committed? |
| --- | --- | --- |
| `~/.claude/settings.json` | user, all projects | no |
| `.claude/settings.json` | project, whole team | yes — treat as code |
| `.claude/settings.local.json` | project, this machine | no (gitignore it) |
| managed policy | organization | admin-controlled |
| plugin / skill / subagent frontmatter | scoped to that component | with the component |

Hook entries merge **additively** — every matching hook from every layer runs; a
project file cannot remove a user hook. `"disableAllHooks": true` follows normal
settings precedence (so a project `false` overrides a user `true`; `--settings
'{"disableAllHooks": true}'` wins for one run) and can never disable managed
hooks from outside managed settings. There is no way to disable one hook while
keeping it configured.

## Coverage gaps

- `Edit|Write|NotebookEdit` never fires for shell-driven edits (`sed -i`,
  `cat >`, heredocs). Mitigations: the Stop-hook worktree scan once per turn (the
  shipped gate), or a `FileChanged` watch on the paths that matter.
- An agent with write access to the settings file can edit its own guardrails —
  keep settings behind CODEOWNERS, treat changes as code review, and consider a
  `ConfigChange` hook on `project_settings` that denies mid-session edits. The
  threat is not hypothetical: the keyv/cacheable npm worm (2026-08-04) planted
  `.claude/settings.json` and `.vscode/tasks.json` hooks in host repos as
  persistence — a committed hooks file is code that runs on every clone, in
  both directions.
- Command-string guards are bypassable via aliases, functions and `eval`; the
  shipped lexer closes the cheap holes (wrappers, `bash -c`, newlines, argument
  order) but is still a convenience, not a boundary — whitelist utilities rather
  than blacklisting patterns where it matters.
- `/rewind` checkpoints track Edit/Write only — bash file operations bypass the
  rollback net too (verify against the checkpointing docs for your version).

## Version notes (release pages, 2026)

- 2.1.143 (May): the 8-consecutive-blocks Stop backstop. 2.1.163 (June):
  `Stop`/`SubagentStop` accept `hookSpecificOutput.additionalContext`.
- 2.1.191 / 2.1.195 (June): comma-separated matchers fixed; hyphenated names
  became exact matches (before that `code-review` was a regex).
- 2.1.214 (July): exit 2 keeps blocking even when stdout JSON fails schema
  validation (older builds could be talked out of a block by bad JSON).
- 2.1.248 (Aug): stdout that looks like a JSON object but does not parse is a
  parse error, not silently plain text. 2.1.251 (Aug): `PreModelSwitch` /
  `PostModelSwitch`. 2.1.257 (Sep): a project or local `permissions.defaultMode:
  bypassPermissions` is ignored — a repo can no longer grant itself bypass.
- Plain-text stdout becomes context only on `SessionStart`, `UserPromptSubmit`,
  `UserPromptExpansion` and `PostModelSwitch`; on every other event use JSON.

## Known issues and version drift

Community-reported, some single-source, all `anthropics/claude-code` issues and
all closed at the time of writing — verify against your installed version:

- #24327 — a PreToolUse exit-2 could make the agent stop cold rather than retry
  with the error (reason to keep hard denies rare and their stderr actionable).
- #13744 — PreToolUse blocking reported working for Bash but not Write/Edit in
  some builds (single-source).
- #19009 — PostToolUse "blocking error" label shown while the edit succeeded
  anyway (by design: PostToolUse cannot block).
- #10412 — plugin-installed hooks reportedly behaved differently from
  `.claude/hooks/` ones (single-source; workaround: keep scripts in `.claude/hooks/`).
- #55334 — reports that sync PreToolUse blocking needed `{"continue": false}` +
  exit 0 instead of exit 2 in some versions — conflicts with the mainline
  contract; test on your version.
- #34600 — intentional exit-2 blocks render as scary "errors" in the UI; closed
  not-planned; set team expectations.

## Debugging checklist

1. Run the script standalone with realistic stdin JSON; confirm the exit code and
   that the reason is on stderr (or in JSON `reason`).
2. `/hooks` — read-only view of what is actually configured after merging.
3. Matcher case and regex anchoring; settings nesting (three levels).
4. `python3` on PATH? `$CLAUDE_PROJECT_DIR` used instead of `$HOME`? Script path
   correct (a `python3 <path>` invocation needs no executable bit)?
5. An exit-0 warning that "never shows up" went to stderr — use `systemMessage`.
6. `PostToolUse` fires only when the tool succeeded; handle the tool's failure
   path with `PostToolUseFailure` if you need it.

## Sources

- Hooks reference — https://code.claude.com/docs/en/hooks
- Hooks guide — https://code.claude.com/docs/en/hooks-guide
- Reference configs — https://github.com/trailofbits/claude-code-config
