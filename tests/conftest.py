import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
import sys
import types
import databricks

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

import main

@pytest.fixture(autouse=True)
def mock_lifespan(monkeypatch):
    monkeypatch.setattr(main, "init_pg_pool", AsyncMock())
    monkeypatch.setattr(main, "close_pg_pool", AsyncMock())

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value.run_sync = AsyncMock()

    fake_engine = MagicMock()
    fake_engine.begin.return_value = mock_context
    fake_engine.dispose = AsyncMock()
    monkeypatch.setattr(main, "engine", fake_engine)

    wc = MagicMock()
    wc.config.token = "token"
    wc.config.host = "http://localhost"
    monkeypatch.setattr(main, "get_workspace_client", lambda: wc)

    mock_ai = MagicMock()
    mock_ai.aclose = AsyncMock()
    monkeypatch.setattr(main, "AsyncOpenAI", lambda **_: mock_ai)

    monkeypatch.setattr(main, "init_vector_index", lambda: None)
    monkeypatch.setattr(main, "vector_index", MagicMock())

    fake_metadata = MagicMock()
    fake_metadata.create_all = AsyncMock()
    fake_model = MagicMock()
    fake_model.metadata = fake_metadata
    monkeypatch.setattr(main, "TodoBase", fake_model)
    import modules.todo.controllers as todo_ctrl
    monkeypatch.setattr(todo_ctrl, "engine", fake_engine)
    monkeypatch.setattr(todo_ctrl, "Base", fake_model)

    yield


@pytest.fixture
def test_client():
    with TestClient(main.app) as client:
        yield client
