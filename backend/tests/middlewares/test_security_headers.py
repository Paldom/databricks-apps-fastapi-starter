"""Security headers: CSP must support the SPA without inline scripts."""

from fastapi.testclient import TestClient

import app.main as app_main


def _headers():
    with TestClient(app_main.app) as client:
        return client.get("/api/health/live").headers


def test_csp_allows_spa_needs_and_bans_inline_scripts():
    csp = _headers()["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "'unsafe-inline'" not in csp.split("style-src")[0]  # scripts: never
    assert "https://fonts.googleapis.com" in csp  # stylesheet origin
    assert "https://fonts.gstatic.com" in csp  # font files origin


def test_baseline_headers_present():
    headers = _headers()
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "SAMEORIGIN"
    assert "max-age" in headers["strict-transport-security"]
    # Static assets manage their own caching; the middleware must not force one.
    assert "cache-control" not in headers
