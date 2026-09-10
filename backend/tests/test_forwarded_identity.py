"""Forwarded identity headers are trusted only inside Databricks Apps or non-production."""

from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as app_main
from app.core.config import settings

HEADERS = {"X-Forwarded-User": "forged-user", "X-Forwarded-Email": "forged@example.com"}


def test_headers_ignored_in_production_outside_apps(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "databricks_app_name", None)
    monkeypatch.setattr(settings, "enable_local_dev_auth_fallback", False)
    with TestClient(app_main.app) as client:
        response = client.get("/api/me", headers=HEADERS)
    assert response.status_code == 401


def test_headers_trusted_inside_databricks_apps(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "databricks_app_name", "my-app")
    monkeypatch.setattr(settings, "enable_local_dev_auth_fallback", False)
    with TestClient(app_main.app) as client:
        response = client.get("/api/me", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["id"] == "forged-user"
