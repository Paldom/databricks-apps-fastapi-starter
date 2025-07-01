import os
import sys
from unittest.mock import MagicMock
import pytest


def test_on_start_sets_headers(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setitem(sys.modules, "openai", MagicMock())
    monkeypatch.setattr("gevent.monkey.patch_all", lambda *a, **k: None)
    locust = pytest.importorskip("locust")
    environment_cls = locust.env.Environment
    from tests.performance.locustfile import DatabricksAppsUser

    class DummyCfg:
        def authenticate(self):
            return {"Authorization": "Bearer x"}

    class DummyWS:
        def __init__(self, *_, **__):
            self.config = DummyCfg()

    monkeypatch.setattr("tests.performance.locustfile.WorkspaceClient", DummyWS)
    env = environment_cls()
    user = DatabricksAppsUser(env)
    user.client = MagicMock()
    user.on_start()
    assert user.headers == {"Authorization": "Bearer x"}
