import pytest
from unittest.mock import MagicMock

from app.core.db.url import get_database_url


def _make_settings(**kwargs):
    s = MagicMock()
    s.database_url = kwargs.get("database_url")
    s.pg_host = kwargs.get("pg_host", "db.example.com")
    s.pg_port = kwargs.get("pg_port", 5432)
    s.pg_database = kwargs.get("pg_database", "mydb")
    s.pg_user = kwargs.get("pg_user", "admin")
    s.pg_password = kwargs.get("pg_password", "secret")
    return s


def test_builds_url_from_pg_settings():
    url = get_database_url(_make_settings())
    assert url == "postgresql+asyncpg://admin:secret@db.example.com:5432/mydb"


def test_database_url_setting_takes_precedence():
    s = _make_settings(database_url="postgresql+asyncpg://override:pass@host/db")
    assert get_database_url(s) == "postgresql+asyncpg://override:pass@host/db"


def test_pg_settings_with_custom_port():
    assert "5433" in get_database_url(_make_settings(pg_port=5433))


def test_builds_url_without_password_for_oauth():
    """When no password is set (Lakebase OAuth flow), URL is built with empty password."""
    url = get_database_url(_make_settings(pg_password=None))
    assert url == "postgresql+asyncpg://admin:@db.example.com:5432/mydb"


def test_raises_when_no_config():
    s = _make_settings(pg_host=None, pg_database=None, pg_user=None, pg_password=None)
    with pytest.raises(ValueError, match="DATABASE_URL or PG"):
        get_database_url(s)
