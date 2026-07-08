# Shared helper: forward a git hook to the user's global core.hooksPath hooks
# (e.g. Databricks' managed gitleaks/secret-scanning hooks) before running any
# repo-specific checks. Husky sets a repo-local core.hooksPath, which would
# otherwise silently bypass those hooks.
#
# Usage: chain_global_hook <hook-name> [args...]  (stdin is passed through)
chain_global_hook() {
  hook_name="$1"
  shift
  global_hooks="$(git config --global core.hooksPath 2>/dev/null || true)"
  if [ -n "$global_hooks" ] && [ -x "$global_hooks/$hook_name" ]; then
    "$global_hooks/$hook_name" "$@" || exit $?
  fi
}
