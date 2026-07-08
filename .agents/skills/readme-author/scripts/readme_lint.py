#!/usr/bin/env python3
"""Lint a README against the structural rules in references/readme-playbook.md.

Usage: readme_lint.py [path/to/README.md]   (default: ./README.md)
Prints ERROR/WARN lines; exit 1 if any ERROR, else 0. Stdlib only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FENCE_RE = re.compile(r"^(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
# A badge is an image served by a badge/status service - screenshots don't count.
BADGE_URL_RE = re.compile(r"(shields\.io|badge\.svg|badgen\.net|/badge/|codecov\.io|"
                          r"coveralls\.io|img\.shields|/actions/workflows/[^)]*badge)", re.I)
PLACEHOLDER_ANGLE_RE = re.compile(r"<[a-z][a-z0-9-]*(?:-[a-z0-9]+)+>|<(?:placeholder|your-[a-z-]+)>", re.I)
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+?)(?:#[^)]*)?\)")
BAD_LINK_TEXT_RE = re.compile(r"\[\s*(?:click\s+here|here|this\s+link)\s*\]", re.I)
HYPE_RE = re.compile(
    r"\b(blazing(?:ly)?[- ]fast|revolutionary|game[- ]chang\w+|world[- ]class|"
    r"cutting[- ]edge|next[- ]generation|ultimate)\b", re.I)
TOKEN_RE = re.compile(r"\{\{[A-Z_]+\}\}")
TODO_RE = re.compile(r"\b(TODO|FIXME|XXX)\b")


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("README.md")
    if not path.is_file():
        print(f"ERROR: {path} not found")
        return 1
    raw = path.read_bytes()
    errors: list[str] = []
    warns: list[str] = []
    if len(raw) > 500 * 1024:
        errors.append(f"file is {len(raw) // 1024} KiB - GitHub truncates rendered READMEs above 500 KiB")
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()

    # Pass 1: headings and fences (~~~ or ``` of any length; info strings allowed).
    fenced = False
    headings: list[tuple[int, int, str]] = []  # (line_no, level, text)
    fence_at: set[int] = set()
    for i, ln in enumerate(lines, 1):
        if FENCE_RE.match(ln.lstrip()):
            fenced = not fenced
            fence_at.add(i)
            continue
        if fenced:
            fence_at.add(i)
            continue
        m = HEADING_RE.match(ln)
        if m:
            headings.append((i, len(m.group(1)), m.group(2).strip()))
    h1s = [h for h in headings if h[1] == 1]
    if not h1s:
        errors.append("no H1 - start with `# ProjectName`")
    elif len(h1s) > 1:
        errors.append(f"{len(h1s)} H1 headings (lines {', '.join(str(h[0]) for h in h1s)}) - use exactly one")
    if headings and headings[0][1] != 1:
        errors.append(f"first heading (line {headings[0][0]}) is not the H1")

    # Badge discipline: count badge-service images near the top (screenshots exempt).
    badge_count = sum(1 for ln in lines[:15] for m in IMAGE_RE.finditer(ln)
                      if BADGE_URL_RE.search(m.group(1)))
    if badge_count > 5:
        errors.append(f"{badge_count} badges in the first 15 lines - cap at 5 trust badges")

    # Quick start visible early.
    if not any(FENCE_RE.match(ln) for ln in lines[:60]):
        warns.append("no code block in the first 60 lines - the quick start should be copy-pasteable early")

    # Intro block length: words between H1 and the first H2, excluding badges/images.
    if h1s:
        start = h1s[0][0]
        end = next((h[0] for h in headings if h[1] >= 2 and h[0] > start), len(lines) + 1)
        intro_words = 0
        for i in range(start, end - 1):
            ln = lines[i]
            if i + 1 in fence_at or IMAGE_RE.search(ln):
                continue
            intro_words += len(re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", ln).split())
        if intro_words > 160:
            warns.append(f"intro block before the first ## is ~{intro_words} words - aim under ~120")

    # Line-level checks (outside code fences).
    for i, ln in enumerate(lines, 1):
        if i in fence_at:
            continue
        if BAD_LINK_TEXT_RE.search(ln):
            errors.append(f"line {i}: non-descriptive link text ('click here'/'here') - name the destination")
        if HYPE_RE.search(ln):
            warns.append(f"line {i}: hype word ({HYPE_RE.search(ln).group(1)!r}) - show, don't tell")
        if TOKEN_RE.search(ln):
            errors.append(f"line {i}: unfilled template token {TOKEN_RE.search(ln).group(0)}")
        if TODO_RE.search(ln):
            warns.append(f"line {i}: {TODO_RE.search(ln).group(1)} marker left in the README")
        prose = re.sub(r"`[^`]*`", "", ln)  # inline code spans may legitimately show <angle> args
        if PLACEHOLDER_ANGLE_RE.search(prose):
            warns.append(f"line {i}: template placeholder {PLACEHOLDER_ANGLE_RE.search(prose).group(0)} "
                         "outside a code block - resolve it (allowed only for a not-yet-built project, listed in the summary)")
        for m in LINK_RE.finditer(ln):
            target = m.group(1)
            if re.match(r"(?:https?:|mailto:|ftp:|#|<|\.\./)", target) or target.startswith("//"):
                continue  # external, anchor, repo-relative-up (../../issues style): not verifiable here
            if not (path.parent / target).exists():
                errors.append(f"line {i}: relative link target missing: {target}")

    # Length and TOC.
    if len(lines) > 400:
        has_toc = any(re.search(r"(table of contents|^contents\b)", h[2], re.I) for h in headings)
        if not has_toc:
            warns.append(f"README is {len(lines)} lines with no TOC - add one or move depth into docs/")

    for e in errors:
        print(f"ERROR: {e}")
    for w in warns:
        print(f"WARN: {w}")
    print(f"{'FAIL' if errors else 'OK'}: {len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
