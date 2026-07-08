#!/usr/bin/env bash
# Validate GitHub YAML issue forms against the official schema.
# Usage: validate_forms.sh [template-dir]   (default: .github/ISSUE_TEMPLATE)
# Exits non-zero on schema violations or when no forms exist. config.yml is a
# different schema and is deliberately excluded.
set -euo pipefail

dir="${1:-.github/ISSUE_TEMPLATE}"
if [ ! -d "$dir" ]; then
  echo "ERROR: $dir does not exist - issue forms live in .github/ISSUE_TEMPLATE/" >&2
  exit 1
fi

shopt -s nullglob
forms=()
for f in "$dir"/*.yml "$dir"/*.yaml; do
  case "$(basename "$f")" in
    config.yml|config.yaml) ;;  # template chooser config, not an issue form
    *) forms+=("$f") ;;
  esac
done
if [ ${#forms[@]} -eq 0 ]; then
  echo "ERROR: no issue forms (*.yml) found in $dir" >&2
  exit 1
fi

# Prefer the console script; fall back to module invocation (PATH-independent).
if command -v check-jsonschema >/dev/null 2>&1; then
  runner=(check-jsonschema)
elif python3 -m check_jsonschema --version >/dev/null 2>&1; then
  runner=(python3 -m check_jsonschema)
else
  echo "check-jsonschema not found - installing pinned version..." >&2
  python3 -m pip install --quiet "check-jsonschema==0.36.2"
  runner=(python3 -m check_jsonschema)
fi

"${runner[@]}" --builtin-schema vendor.github-issue-forms "${forms[@]}"
echo "OK: ${#forms[@]} issue form(s) schema-valid"
