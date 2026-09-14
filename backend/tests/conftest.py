import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient  # noqa: E402

import app.main as app_main  # noqa: E402
import app.core.bootstrap as bootstrap  # noqa: E402


@pytest.fixture(autouse=True)
def mock_lifespan(monkeypatch):
    """Patch lifespan-critical resources to avoid real infra."""
    # SQLAlchemy engine (no create_all — Alembic owns schema)
    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()
    monkeypatch.setattr(
        bootstrap,
        "create_async_engine_from_settings",
        lambda s: fake_engine,
    )
    monkeypatch.setattr(
        bootstrap,
        "create_session_factory",
        lambda e: _mock_session_factory(),
    )
    monkeypatch.setattr(bootstrap.settings, "pg_host", "db.example.com")
    monkeypatch.setattr(bootstrap.settings, "pg_database", "starter")
    monkeypatch.setattr(bootstrap.settings, "pg_user", "starter")
    monkeypatch.setattr(bootstrap.settings, "pg_password", "secret")
    monkeypatch.setattr(bootstrap.settings, "environment", "test")
    monkeypatch.setattr(bootstrap.settings, "enable_databricks_integrations", False)
    monkeypatch.setattr(bootstrap.settings, "enable_local_dev_auth_fallback", None)
    monkeypatch.setattr(bootstrap.settings, "local_dev_user_id", "local-dev-user")
    monkeypatch.setattr(bootstrap.settings, "databricks_host", "http://localhost")
    monkeypatch.setattr(bootstrap.settings, "databricks_token", "test-token")
    monkeypatch.setattr(bootstrap.settings, "serving_endpoint_name", "starter-endpoint")
    monkeypatch.setattr(bootstrap.settings, "vector_search_endpoint_name", "starter-vs")
    monkeypatch.setattr(
        bootstrap.settings,
        "vector_search_index_name",
        "main.default.starter_index",
    )
    # No chat_backend setting to override; single LangGraph runtime


def _mock_session_factory():
    """Return a session factory that produces mock sessions.

    The factory supports both context-manager usage (middleware) and
    the get_async_session dependency pattern.
    """
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    # session.begin() — async context manager for transactions
    mock_begin = AsyncMock()
    mock_begin.__aenter__ = AsyncMock(return_value=None)
    mock_begin.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_begin)

    # factory() returns a context manager that yields the session
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = False

    factory = MagicMock(return_value=mock_session_ctx)
    return factory


@pytest.fixture
def test_client():
    with TestClient(app_main.app) as client:
        yield client
