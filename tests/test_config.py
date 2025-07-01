import base64
import types
from config import get_secret

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
    monkeypatch.setattr("workspace.w", lambda: DummyWorkspace(encoded))
    assert get_secret("X", scope="s") == "secret"


def test_get_secret_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("workspace.w", lambda: DummyWorkspace("not-base64"))
    assert get_secret("X", scope="s") is None
