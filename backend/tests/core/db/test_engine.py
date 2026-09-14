"""Engine settings that keep Lakebase connections alive and inside the app's schema."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.core.config import Settings
from app.core.db import engine as engine_module


def test_engine_uses_pool_settings_tls_and_the_app_schema(monkeypatch):
    captured: dict = {}

    def fake_create_async_engine(url, **kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(engine_module, "create_async_engine", fake_create_async_engine)
    settings = Settings(
        PGHOST="h", PGDATABASE="d", PGUSER="u", PGSSLMODE="require", _env_file=None
    )

    engine_module.create_async_engine_from_settings(settings)

    assert captured["pool_pre_ping"] is True
    assert captured["pool_recycle"] < 3600  # OAuth tokens live one hour
    assert captured["connect_args"] == {
        "server_settings": {"search_path": "app"},
        "ssl": "require",
    }


def test_local_postgres_gets_no_tls(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        engine_module,
        "create_async_engine",
        lambda url, **kw: captured.update(kw) or MagicMock(),
    )
    settings = Settings(database_url="postgresql+asyncpg://u:p@h/d", _env_file=None)
    engine_module.create_async_engine_from_settings(settings)
    assert "ssl" not in captured["connect_args"]
