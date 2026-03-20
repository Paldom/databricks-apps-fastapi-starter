import base64
import types
from app.core.config import get_secret


class DummySecret:
    def __init__(self, value):
        self.value = value


class DummyWorkspace:
    def __init__(self, encoded):
        self._encoded = encoded
        self.secrets = types.SimpleNamespace(get_secret=self._get_secret)

    def _get_secret(self, scope, key):
        return DummySecret(self._encoded)


def test_get_secret_decodes_base64(monkeypatch):
    encoded = base64.b64encode(b"secret").decode()
    monkeypatch.setattr(
        "app.core.databricks.workspace.get_workspace_client_singleton",
        lambda: DummyWorkspace(encoded),
    )
    assert get_secret("X", scope="s") == "secret"


def test_get_secret_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(
        "app.core.databricks.workspace.get_workspace_client_singleton",
        lambda: DummyWorkspace("not-base64"),
    )
    assert get_secret("X", scope="s") is None
