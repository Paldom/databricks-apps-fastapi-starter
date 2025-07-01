from fastapi.testclient import TestClient
import main
from unittest.mock import MagicMock


def test_workspace_client_middleware_uses_header(monkeypatch):
    created = {}

    class DummyWC:
        def __init__(self, *, host=None, token=None):
            created['host'] = host
            created['token'] = token

    monkeypatch.setattr(main.settings, "enable_obo", True)

    monkeypatch.setattr('middlewares.workspace_client.w', lambda: MagicMock(config=MagicMock(host='http://h')))
    monkeypatch.setattr('middlewares.workspace_client.WorkspaceClient', DummyWC)

    with TestClient(main.app) as client:
        response = client.get('/v1/userInfo', headers={'X-Forwarded-Access-Token': 'pat'})
    assert response.status_code == 200
    assert created['token'] == 'pat'
    assert created['host'] == 'http://h'


def test_workspace_client_middleware_ignores_header_when_disabled(monkeypatch):
    called = False

    def dummy_wc(*a, **k):
        nonlocal called
        called = True

    monkeypatch.setattr(main.settings, "enable_obo", False)
    monkeypatch.setattr('middlewares.workspace_client.w', lambda: "default")
    monkeypatch.setattr('middlewares.workspace_client.WorkspaceClient', dummy_wc)

    with TestClient(main.app) as client:
        response = client.get('/v1/userInfo', headers={'X-Forwarded-Access-Token': 'ignored'})
    assert response.status_code == 200
    assert not called
