"""Security headers: CSP must support the SPA without inline scripts."""

from urllib.parse import urlsplit

from fastapi.testclient import TestClient

import app.main as app_main


def _hosts(tokens: set[str]) -> set[str]:
    """Hostnames of the URL sources in a CSP directive (parsed, not matched as substrings)."""
    return {urlsplit(token).netloc for token in tokens if token.startswith("https://")}


def _headers():
    with TestClient(app_main.app) as client:
        return client.get("/api/health/live").headers


def test_csp_allows_spa_needs_and_bans_inline_scripts():
    directives = {
        name: set(values)
        for name, *values in (
            part.split() for part in _headers()["content-security-policy"].split(";")
        )
        if name
    }
    assert directives["script-src"] == {"'self'"}  # scripts: same origin, never inline
    assert directives["style-src"] >= {"'self'", "'unsafe-inline'"}
    assert _hosts(directives["style-src"]) == {
        "fonts.googleapis.com"
    }  # stylesheet origin
    assert directives["font-src"] >= {"'self'", "data:"}
    assert _hosts(directives["font-src"]) == {"fonts.gstatic.com"}  # font files origin


def test_baseline_headers_present():
    headers = _headers()
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "SAMEORIGIN"
    assert "max-age" in headers["strict-transport-security"]
    # Static assets manage their own caching; the middleware must not force one.
    assert "cache-control" not in headers
