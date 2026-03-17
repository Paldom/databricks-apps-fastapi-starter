import sys
import types

import pytest
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Module-level stubs for optional dependencies that may not be installed
# in the test environment (vector search, sqlalchemy fallback, etc.)
# ---------------------------------------------------------------------------

import databricks

try:
    import sqlalchemy.ext.asyncio as _sa_asyncio

    sa_asyncio: types.ModuleType | types.SimpleNamespace = _sa_asyncio
except Exception:
    sa_asyncio = types.SimpleNamespace(
        AsyncSession=MagicMock(),
        async_sessionmaker=MagicMock(),
        create_async_engine=MagicMock(),
    )
    sqlalchemy_module = types.ModuleType("sqlalchemy")
    sqlalchemy_module.ext = types.SimpleNamespace(asyncio=sa_asyncio)  # type: ignore[attr-defined]
    sqlalchemy_module.TIMESTAMP = MagicMock()  # type: ignore[attr-defined]
    sqlalchemy_module.String = MagicMock()  # type: ignore[attr-defined]
    sqlalchemy_module.Boolean = MagicMock()  # type: ignore[attr-defined]
    sqlalchemy_module.select = MagicMock()  # type: ignore[attr-defined]
    sqlalchemy_module.orm = types.SimpleNamespace(  # type: ignore[attr-defined]
        DeclarativeBase=type("DeclarativeBase", (), {}),
        Mapped=MagicMock(),
        mapped_column=MagicMock(),
    )
    sys.modules.setdefault("sqlalchemy", sqlalchemy_module)
    sys.modules.setdefault("sqlalchemy.ext", sqlalchemy_module.ext)  # type: ignore[arg-type]
    sys.modules.setdefault("sqlalchemy.ext.asyncio", sa_asyncio)  # type: ignore[arg-type]
    sys.modules.setdefault("sqlalchemy.orm", sqlalchemy_module.orm)  # type: ignore[arg-type]

if not hasattr(sa_asyncio, "async_sessionmaker"):
    sa_asyncio.async_sessionmaker = MagicMock()  # type: ignore[union-attr]

# Provide dummy Databricks vector search modules when not available
vector_module = types.ModuleType("databricks.vector_search")
index_module = types.ModuleType("databricks.vector_search.index")
client_module = types.ModuleType("databricks.vector_search.client")


class DummyVSClient:
    def get_index(self, *a, **k):
        return MagicMock()


client_module.VectorSearchClient = DummyVSClient
index_module.VectorSearchIndex = MagicMock

databricks.vector_search = vector_module

sys.modules.setdefault("databricks.vector_search", vector_module)
sys.modules.setdefault("databricks.vector_search.index", index_module)
sys.modules.setdefault("databricks.vector_search.client", client_module)

# ---------------------------------------------------------------------------
# Now safe to import the application
# ---------------------------------------------------------------------------
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

    # Workspace client
    wc = MagicMock()
    wc.config.token = "test-token"
    wc.config.host = "http://localhost"
    monkeypatch.setattr(bootstrap, "get_workspace_client_singleton", lambda: wc)
    monkeypatch.setattr(bootstrap.settings, "lakebase_host", "db.example.com")
    monkeypatch.setattr(bootstrap.settings, "lakebase_db", "starter")
    monkeypatch.setattr(bootstrap.settings, "lakebase_user", "starter")
    monkeypatch.setattr(bootstrap.settings, "lakebase_password", "secret")
    monkeypatch.setattr(bootstrap.settings, "serving_endpoint_name", "starter-endpoint")
    monkeypatch.setattr(
        bootstrap.settings, "vector_search_endpoint_name", "starter-vs"
    )
    monkeypatch.setattr(
        bootstrap.settings,
        "vector_search_index_name",
        "main.default.starter_index",
    )

    # AI client
    mock_ai = MagicMock()
    mock_ai.aclose = AsyncMock()
    monkeypatch.setattr(bootstrap, "AsyncOpenAI", lambda **_: mock_ai)

    # Vector search
    monkeypatch.setattr(bootstrap, "init_vector_index", lambda s: MagicMock())

    # Cache
    from app.core.cache import NullCache

    monkeypatch.setattr(bootstrap, "build_cache", lambda s: NullCache())

    yield


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
