#!/usr/bin/env bash
# Publish-readiness gate: tarball inspection + publint --strict + arethetypeswrong,
# all run against the SAME packed artifact — packed by the package manager the repo
# actually publishes with (pnpm rewrites workspace: specifiers on pack; npm would not).
# Usage: check_package.sh [package-dir] [existing.tgz]   (default: pack the dir)
# Exits non-zero on any finding. Requires Node >= 18 with npx (no Python needed).
set -uo pipefail

dir="${1:-.}"
given="${2:-}"
cd "$dir" || { echo "ERROR: cannot cd to $dir" >&2; exit 1; }
[ -f package.json ] || { echo "ERROR: no package.json in $dir" >&2; exit 1; }
command -v npx >/dev/null 2>&1 || { echo "ERROR: npx (Node.js >= 18) required" >&2; exit 1; }

# Exact pins: the gate that teaches pinning must not float its own tooling.
# Bump deliberately (check npm for the current release), keep the two in step with CI.
PUBLINT_VERSION="0.3.24"
ATTW_VERSION="0.18.5"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fail=0

if [ -n "$given" ]; then
  tarball="$given"
  echo "== using existing tarball $tarball =="
else
  if [ -f pnpm-lock.yaml ]; then pm=pnpm; elif [ -f yarn.lock ]; then pm=yarn; else pm=npm; fi
  echo "== $pm pack (tarball contents) =="
  case "$pm" in
    pnpm) pnpm pack --pack-destination "$tmp" >"$tmp/pack.out" 2>&1 ;;
    yarn) yarn pack --out "$tmp/package.tgz" >"$tmp/pack.out" 2>&1 ;;
    npm)  npm pack --pack-destination "$tmp" >"$tmp/pack.out" 2>&1 ;;
  esac || { cat "$tmp/pack.out" >&2; echo "ERROR: $pm pack failed" >&2; exit 1; }
  tarball="$(ls "$tmp"/*.tgz 2>/dev/null | head -1)"
  [ -n "$tarball" ] || { echo "ERROR: $pm pack produced no tarball" >&2; exit 1; }
fi

# The tarball itself is the source of truth for what ships — not `files`, not the PM's summary.
files="$(tar -tzf "$tarball" | sed 's#^package/##')"
echo "$(printf '%s\n' "$files" | grep -c .) files in tarball"
bad="$(printf '%s\n' "$files" | grep -E '(^|/)(\.env[^/]*$|\.local/|node_modules/|\.github/|coverage/|\.DS_Store$)|\.(test|spec)\.[cm]?[jt]sx?$' || true)"
if [ -n "$bad" ]; then
  echo "ERROR: tarball contains files that should not ship:"
  printf '  - %s\n' $bad
  echo "ERROR: fix the files whitelist (package.json#files)" >&2
  fail=1
fi

echo "== publint --strict (against the packed tarball) =="
if ! npx -y "publint@${PUBLINT_VERSION}" --strict "$tarball"; then
  echo "ERROR: publint --strict reported problems" >&2
  fail=1
fi

echo "== arethetypeswrong (against the same tarball) =="
if ! npx -y "@arethetypeswrong/cli@${ATTW_VERSION}" "$tarball"; then
  echo "ERROR: arethetypeswrong reported resolution problems" >&2
  fail=1
fi

[ "$fail" -eq 0 ] && echo "OK: tarball, publint --strict, and attw all clean"
exit "$fail"
