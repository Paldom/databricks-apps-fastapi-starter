#!/usr/bin/env python3
"""Lint a .pre-commit-config.yaml for known footguns. Read-only: never edits.

Uses only the standard library (no PyYAML): a tolerant line-based parse of the
regular structure pre-commit configs actually use. Unrecognized constructs are
skipped, never fatal.

Checks
  errors (exit 1):
    E001  repo points at archived pre-commit/mirrors-prettier (use rbubley fork)
    E002  remote repo has no rev, or rev is a mutable ref (main/master/HEAD/...)
    E003  'typescript' used as a file type (identify's identifier is 'ts')
  warnings (exit 0, or 1 with --strict):
    N202  ruff --fix without --exit-non-zero-on-fix (harmless under pre-commit, which fails
          modifying hooks itself; the flag matters only when the command also runs outside)
    W102  ruff-format ordered before the ruff lint hook (reformat churn)
    W103  mirrors-mypy hook without additional_dependencies (isolated env
          lacks project deps; false import errors or silently missing stubs)
    W104  prettier hook without types/types_or scoping (may collide with ruff)
    W105  hook uses a stage that default_install_hook_types does not install
    W106  legacy stage name (commit/push) - renamed pre-commit/pre-push in v3.2
  notes (never affect exit):
    N201  tag-pinned revs (info: `pre-commit autoupdate --freeze` pins to SHAs)

Usage:
    python3 check_precommit_config.py [path/to/.pre-commit-config.yaml] [--strict]

Exit codes: 0 = clean (warnings allowed unless --strict), 1 = findings, 2 = usage/IO.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MUTABLE_REVS = {"main", "master", "head", "latest", "develop", "trunk", ""}
LEGACY_STAGES = {"commit": "pre-commit", "push": "pre-push", "merge-commit": "pre-merge-commit"}
DEFAULT_INSTALLED = {"pre-commit"}  # what plain `pre-commit install` wires up
RUFF_LINT_IDS = {"ruff", "ruff-check"}


def clean(value: str) -> str:
    """Strip trailing comment and surrounding quotes from a scalar value."""
    value = value.strip()
    if value and value[0] in "'\"":
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end != -1 else value[1:]
    cut = re.search(r"\s#", value)
    if cut:
        value = value[: cut.start()].rstrip()
    return value


def parse_list(inline: str, block_items: list[str]) -> list[str]:
    """Parse a flow list ('[a, b]') or collected block items into strings."""
    inline = inline.strip()
    if inline.startswith("[") and inline.endswith("]"):
        inner = inline[1:-1]
        return [clean(part) for part in inner.split(",") if clean(part)]
    return [clean(item) for item in block_items if clean(item)]


@dataclass
class Hook:
    hook_id: str
    line: int
    keys: dict[str, tuple[str, list[str], int]] = field(default_factory=dict)
    # key -> (inline_value, block_list_items, line_number)

    def list_of(self, key: str) -> list[str]:
        if key not in self.keys:
            return []
        inline, block, _ = self.keys[key]
        return parse_list(inline, block)


@dataclass
class Repo:
    url: str
    line: int
    rev: str | None = None
    rev_line: int = 0
    hooks: list[Hook] = field(default_factory=list)


def parse_config(lines: list[str]) -> tuple[list[Repo], list[str] | None]:
    """Return (repos, default_install_hook_types or None)."""
    repos: list[Repo] = []
    diht: list[str] | None = None
    diht_block: list[str] = []
    diht_pending = False
    repo: Repo | None = None
    hook: Hook | None = None
    pending_key: str | None = None  # hook key awaiting block-list items

    for n, raw in enumerate(lines, start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        text = raw.strip()

        if indent == 0:
            diht_pending = False
            m = re.match(r"^default_install_hook_types:\s*(.*)$", text)
            if m:
                value = m.group(1).strip()
                if value.startswith("["):
                    diht = parse_list(value, [])
                else:
                    diht_pending = True  # block list follows
                    diht = []
                continue
            if not text.startswith("- "):
                pending_key = None
                continue

        if diht_pending and text.startswith("- "):
            diht_block.append(text[2:])
            if diht is not None:
                diht = parse_list("", diht_block)
            continue
        diht_pending = False

        m = re.match(r"^-\s+repo:\s*(.+)$", text)
        if m:
            repo = Repo(url=clean(m.group(1)).rstrip("/"), line=n)
            repos.append(repo)
            hook = None
            pending_key = None
            continue
        if repo is None:
            continue

        m = re.match(r"^rev:\s*(.+)$", text)
        if m and hook is None:
            repo.rev, repo.rev_line = clean(m.group(1)), n
            continue

        m = re.match(r"^-\s+id:\s*(.+)$", text)
        if m:
            hook = Hook(hook_id=clean(m.group(1)), line=n)
            repo.hooks.append(hook)
            pending_key = None
            continue

        if hook is not None:
            m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", text)
            if m:
                key, value = m.group(1), m.group(2).strip()
                hook.keys[key] = (value, [], n)
                pending_key = key if not value else None
                continue
            if pending_key and text.startswith("- "):
                hook.keys[pending_key][1].append(text[2:])
                continue
        pending_key = None
    return repos, diht


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "path",
        nargs="?",
        default=".pre-commit-config.yaml",
        help="config to check (default: ./.pre-commit-config.yaml)",
    )
    parser.add_argument("--strict", action="store_true", help="warnings also fail")
    args = parser.parse_args()

    path = Path(args.path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"ERROR {path}: cannot read config: {exc}", file=sys.stderr)
        return 2

    repos, diht = parse_config(lines)
    if not repos:
        print(
            f"ERROR {path}:1: E000 no `- repo:` entries found — not a pre-commit config?",
            file=sys.stderr,
        )
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []
    tag_pinned = 0
    installed = set(diht) if diht is not None else set(DEFAULT_INSTALLED)

    for repo in repos:
        local = repo.url in ("local", "meta")

        if repo.url.endswith("pre-commit/mirrors-prettier"):
            errors.append(
                f"{path}:{repo.line}: E001 pre-commit/mirrors-prettier is "
                "archived (broken since Prettier v3) — use "
                "https://github.com/rbubley/mirrors-prettier"
            )

        if not local:
            rev = (repo.rev or "").strip()
            if rev.lower() in MUTABLE_REVS or rev.startswith("refs/heads/"):
                errors.append(
                    f"{path}:{repo.rev_line or repo.line}: E002 repo {repo.url} "
                    f"has {'no rev' if not rev else f'mutable rev {rev!r}'} — "
                    "pin a tag or full commit SHA for reproducibility"
                )
            elif not SHA_RE.match(rev):
                tag_pinned += 1

        lint_seen_at: int | None = None
        for idx, hook in enumerate(repo.hooks):
            hid = hook.hook_id

            for key in ("types", "types_or"):
                if "typescript" in [t.lower() for t in hook.list_of(key)]:
                    errors.append(
                        f"{path}:{hook.keys[key][2]}: E003 file type 'typescript' "
                        "does not exist in identify — use 'ts' (silently matches "
                        "nothing as written)"
                    )

            if hid in RUFF_LINT_IDS:
                lint_seen_at = idx
                hook_args = hook.list_of("args")
                if "--fix" in hook_args and "--exit-non-zero-on-fix" not in hook_args:
                    notes.append(
                        f"{path}:{hook.line}: N202 ruff --fix without --exit-non-zero-on-fix — "
                        "harmless here (pre-commit fails any hook that modifies files); add the "
                        "flag only if the same command also runs outside pre-commit"
                    )

            if (
                hid == "ruff-format"
                and lint_seen_at is None
                and any(h.hook_id in RUFF_LINT_IDS for h in repo.hooks)
            ):
                warnings.append(
                    f"{path}:{hook.line}: W102 ruff-format runs before the ruff "
                    "lint hook — order fixer first, formatter second, or fixes "
                    "get reformatted in a second pass"
                )

            if (
                repo.url.endswith("pre-commit/mirrors-mypy")
                and "additional_dependencies" not in hook.keys
            ):
                warnings.append(
                    f"{path}:{hook.line}: W103 mirrors-mypy without "
                    "additional_dependencies — the isolated env has none of your "
                    "project's deps/stubs; add them or use a local `uv run mypy` hook"
                )

            if hid == "prettier" and "types" not in hook.keys and "types_or" not in hook.keys:
                warnings.append(
                    f"{path}:{hook.line}: W104 prettier hook is not scoped — add "
                    "types_or: [yaml, markdown, json] so it never touches Python files"
                )

            for stage in hook.list_of("stages"):
                if stage in LEGACY_STAGES:
                    warnings.append(
                        f"{path}:{hook.keys['stages'][2]}: W106 legacy stage name "
                        f"{stage!r} — renamed {LEGACY_STAGES[stage]!r} in pre-commit 3.2"
                    )
                    stage = LEGACY_STAGES[stage]
                if (
                    stage
                    in (
                        "commit-msg",
                        "pre-push",
                        "pre-merge-commit",
                        "post-checkout",
                        "post-commit",
                        "post-merge",
                        "post-rewrite",
                        "prepare-commit-msg",
                    )
                    and stage not in installed
                ):
                    warnings.append(
                        f"{path}:{hook.keys['stages'][2]}: W105 hook "
                        f"{hid!r} uses stage {stage!r} but "
                        f"{'default_install_hook_types omits it' if diht is not None else 'there is no default_install_hook_types'}"
                        " — plain `pre-commit install` will never install it and "
                        "the hook silently won't run"
                    )

    if tag_pinned:
        notes.append(
            f"{path}: N201 {tag_pinned} repo(s) pinned by tag — fine for most repos; "
            "`pre-commit autoupdate --freeze` pins full SHAs (tags can be re-pointed)"
        )

    for line in errors:
        print(f"ERROR {line}", file=sys.stderr)
    for line in warnings:
        print(f"WARN  {line}", file=sys.stderr)
    for line in notes:
        print(f"NOTE  {line}")

    failed = bool(errors) or (args.strict and bool(warnings))
    print(f"{'FAIL' if failed else 'OK'}: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
