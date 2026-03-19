import os

import pytest
from unittest.mock import MagicMock

from app.core.db.url import get_database_url


def _make_settings(**kwargs):
    s = MagicMock()
    s.pg_host = kwargs.get("pg_host", "db.example.com")
    s.pg_port = kwargs.get("pg_port", 5432)
    s.pg_database = kwargs.get("pg_database", "mydb")
    s.pg_user = kwargs.get("pg_user", "admin")
    s.pg_password = kwargs.get("pg_password", "secret")
    return s


def test_builds_url_from_pg_settings(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = _make_settings()
    url = get_database_url(s)
    assert url == "postgresql+asyncpg://admin:secret@db.example.com:5432/mydb"


def test_database_url_env_takes_precedence(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://override:pass@host/db")
    s = _make_settings()
    url = get_database_url(s)
    assert url == "postgresql+asyncpg://override:pass@host/db"


def test_pg_settings_with_custom_port(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = _make_settings(pg_port=5433)
    url = get_database_url(s)
    assert "5433" in url


def test_raises_when_no_config(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = MagicMock()
    s.pg_host = None
    s.pg_database = None
    s.pg_user = None
    s.pg_password = None
    with pytest.raises(ValueError, match="DATABASE_URL or PG"):
        get_database_url(s)
