import os

import pytest
from unittest.mock import MagicMock

from app.core.db.url import get_database_url


def _make_settings(**kwargs):
    s = MagicMock()
    s.lakebase_host = kwargs.get("host", "db.example.com")
    s.lakebase_port = kwargs.get("port", 5432)
    s.lakebase_db = kwargs.get("db", "mydb")
    s.lakebase_user = kwargs.get("user", "admin")
    s.lakebase_password = kwargs.get("password", "secret")
    return s


def test_builds_url_from_settings():
    s = _make_settings()
    url = get_database_url(s)
    assert url == "postgresql+asyncpg://admin:secret@db.example.com:5432/mydb"


def test_database_url_env_takes_precedence(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://override:pass@host/db")
    s = _make_settings()
    url = get_database_url(s)
    assert url == "postgresql+asyncpg://override:pass@host/db"


def test_custom_port():
    s = _make_settings(port=5433)
    url = get_database_url(s)
    assert "5433" in url
