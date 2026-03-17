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
    import sqlalchemy.ext.asyncio as sa_asyncio
except Exception:
    sa_asyncio = types.SimpleNamespace(
        AsyncSession=MagicMock(),
        async_sessionmaker=MagicMock(),
        create_async_engine=MagicMock(),
    )
    sqlalchemy_module = types.ModuleType("sqlalchemy")
    sqlalchemy_module.ext = types.SimpleNamespace(asyncio=sa_asyncio)
    sqlalchemy_module.TIMESTAMP = MagicMock()
    sqlalchemy_module.String = MagicMock()
    sqlalchemy_module.Boolean = MagicMock()
    sqlalchemy_module.select = MagicMock()
    sqlalchemy_module.orm = types.SimpleNamespace(
        DeclarativeBase=type("DeclarativeBase", (), {}),
        Mapped=MagicMock(),
        mapped_column=MagicMock(),
    )
    sys.modules.setdefault("sqlalchemy", sqlalchemy_module)
    sys.modules.setdefault("sqlalchemy.ext", sqlalchemy_module.ext)
    sys.modules.setdefault("sqlalchemy.ext.asyncio", sa_asyncio)
    sys.modules.setdefault("sqlalchemy.orm", sqlalchemy_module.orm)

if not hasattr(sa_asyncio, "async_sessionmaker"):
    sa_asyncio.async_sessionmaker = MagicMock()

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
    # Database pool (must have async close method)
    mock_pool = MagicMock()
    mock_pool.close = AsyncMock()
    monkeypatch.setattr(bootstrap, "create_pg_pool", AsyncMock(return_value=mock_pool))

    # SQLAlchemy engine
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value.run_sync = AsyncMock()
    fake_engine = MagicMock()
    fake_engine.begin.return_value = mock_context
    fake_engine.dispose = AsyncMock()
    monkeypatch.setattr(bootstrap, "create_engine", lambda s: fake_engine)
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

    # Patch workspace_client middleware too
    import app.middlewares.workspace_client as ws_mw
    monkeypatch.setattr(ws_mw, "get_workspace_client_singleton", lambda: wc)

    # AI client
    mock_ai = MagicMock()
    mock_ai.aclose = AsyncMock()
    monkeypatch.setattr(bootstrap, "AsyncOpenAI", lambda **_: mock_ai)

    # Vector search
    monkeypatch.setattr(bootstrap, "init_vector_index", lambda s: MagicMock())

    yield


def _mock_session_factory():
    """Return a session factory that produces mock sessions (for auth middleware)."""
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    factory = MagicMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = False
    factory.return_value = mock_session_ctx
    return factory


@pytest.fixture
def test_client():
    with TestClient(app_main.app) as client:
        yield client
