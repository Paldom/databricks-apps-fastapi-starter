# Security Policy

## Supported Versions

This is a starter template, not a released library. Only the latest state of the
`main` branch is supported; there are no maintained release lines. If you have
forked the template, apply fixes from `main` to your fork.

| Version       | Supported          |
| ------------- | ------------------ |
| `main` (HEAD) | :white_check_mark: |
| anything else | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions, or pull requests.**

Instead, use one of these channels:

1. **GitHub private vulnerability reporting** (preferred):
   [Report a vulnerability](https://github.com/Paldom/databricks-apps-fastapi-starter/security/advisories/new)
   via the repository's Security tab.
2. If private reporting is unavailable, contact the maintainer
   ([@Paldom](https://github.com/Paldom)) directly and ask for a secure channel
   before sharing details.

Please include, where possible:

- A description of the issue and the affected component (file path, endpoint,
  workflow, or dependency).
- Steps to reproduce or a proof of concept.
- The potential impact (what an attacker could achieve).
- Any suggested remediation.

## What to Expect

- Acknowledgement of your report, typically within 7 days.
- An assessment of the issue and, if confirmed, a fix on `main`.
- Credit in the advisory/changelog if you would like it (tell us how you want
  to be credited).

This project is maintained on a best-effort basis; there is no bug bounty.

## Scope Notes

- Secrets committed to this repository are treated as compromised: if you find
  one, report it — the credential will be rotated first, before any history
  cleanup.
- Vulnerabilities in third-party dependencies are handled via Dependabot
  alerts/updates; reports about a dependency CVE with no exploitable path in
  this template may be closed as informational.
- This template deploys to Databricks Apps. Issues in the Databricks platform
  itself should be reported to
  [Databricks security](https://www.databricks.com/trust/security), not here.
