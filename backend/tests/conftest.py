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

# Provide stubs for optional packages when not installed.
_OPTIONAL_STUBS = [
    "langchain_core",
    "langchain_core.messages",
    "langchain_core.messages.base",
    "langchain_core.language_models",
    "langchain_core.language_models.chat_models",
    "langchain_core.tools",
    "langchain_core.tools.base",
    "langchain_core.runnables",
    "langchain_core.runnables.base",
    "langchain_core.prompt_values",
    "langchain_openai",
    "langgraph",
    "langgraph.graph",
    "langgraph.graph.message",
    "langgraph.graph.state",
    "langgraph.prebuilt",
    "langgraph.prebuilt.tool_node",
    "langgraph.checkpoint",
    "langgraph.checkpoint.base",
    "langgraph.checkpoint.memory",
    "langgraph.runtime",
    "langgraph._internal",
    "langgraph._internal._runnable",
    "mlflow",
    "mlflow.langchain",
    "mlflow.openai",
    "mlflow.genai",
    "mlflow.genai.agent_server",
    "mlflow.types",
    "mlflow.types.responses",
    "mlflow.pyfunc",
    "mlflow.entities",
    "mlflow.models",
]
for mod_name in _OPTIONAL_STUBS:
    if mod_name not in sys.modules:
        try:
            __import__(mod_name)
        except ImportError:
            stub = types.ModuleType(mod_name)
            # Commonly referenced names
            for attr in (
                "BaseChatModel", "BaseTool", "ToolNode", "StateGraph", "AnyMessage",
                "HumanMessage", "SystemMessage", "AIMessage", "ChatOpenAI",
                "MemorySaver", "BaseCheckpointSaver", "CompiledStateGraph",
                "set_experiment", "update_current_trace", "autolog", "trace",
                "create_react_agent", "BaseStore",
                "ResponsesAgent", "set_model", "SpanType",
            ):
                setattr(stub, attr, MagicMock)
            stub.tool = lambda f=None, **kw: f if f else (lambda fn: fn)  # type: ignore[attr-defined]
            stub.END = "__end__"  # type: ignore[attr-defined]
            stub.add_messages = MagicMock  # type: ignore[attr-defined]
            stub.get_active_trace_id = MagicMock(return_value=None)  # type: ignore[attr-defined]
            sys.modules[mod_name] = stub

# Ensure mlflow.types.responses has proper Pydantic models for contracts
try:
    from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse
except (ImportError, AttributeError):
    # Build minimal Pydantic stubs so agent contracts work in tests
    from pydantic import BaseModel as _BM

    class _ResponsesAgentRequest(_BM):
        input: list = []
        custom_inputs: dict = {}

    class _ResponsesAgentResponse(_BM):
        output: list = []
        custom_outputs: dict = {}

    class _ResponsesAgentStreamEvent(_BM):
        type: str = ""

    _resp_mod = sys.modules.get("mlflow.types.responses")
    if _resp_mod is None:
        _resp_mod = types.ModuleType("mlflow.types.responses")
        sys.modules["mlflow.types.responses"] = _resp_mod
    _resp_mod.ResponsesAgentRequest = _ResponsesAgentRequest  # type: ignore[attr-defined]
    _resp_mod.ResponsesAgentResponse = _ResponsesAgentResponse  # type: ignore[attr-defined]
    _resp_mod.ResponsesAgentStreamEvent = _ResponsesAgentStreamEvent  # type: ignore[attr-defined]

    _types_mod = sys.modules.get("mlflow.types")
    if _types_mod is None:
        _types_mod = types.ModuleType("mlflow.types")
        sys.modules["mlflow.types"] = _types_mod
    _types_mod.responses = _resp_mod  # type: ignore[attr-defined]

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
    monkeypatch.setattr(bootstrap.settings, "pg_host", "db.example.com")
    monkeypatch.setattr(bootstrap.settings, "pg_database", "starter")
    monkeypatch.setattr(bootstrap.settings, "pg_user", "starter")
    monkeypatch.setattr(bootstrap.settings, "pg_password", "secret")
    monkeypatch.setattr(bootstrap.settings, "environment", "test")
    monkeypatch.setattr(
        bootstrap.settings, "enable_databricks_integrations", False
    )
    monkeypatch.setattr(
        bootstrap.settings, "enable_local_dev_auth_fallback", None
    )
    monkeypatch.setattr(bootstrap.settings, "local_dev_user_id", "local-dev-user")
    monkeypatch.setattr(bootstrap.settings, "databricks_host", "http://localhost")
    monkeypatch.setattr(bootstrap.settings, "databricks_token", "test-token")
    monkeypatch.setattr(bootstrap.settings, "serving_endpoint_name", "starter-endpoint")
    monkeypatch.setattr(
        bootstrap.settings, "vector_search_endpoint_name", "starter-vs"
    )
    monkeypatch.setattr(
        bootstrap.settings,
        "vector_search_index_name",
        "main.default.starter_index",
    )
    # No chat_backend setting to override; single LangGraph runtime

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
