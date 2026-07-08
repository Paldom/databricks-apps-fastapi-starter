"""Examples module: activation contract and internal configuration guards.

The examples module mounts only when ``ENABLE_DATABRICKS_INTEGRATIONS`` is
set (module mechanism, DESIGN.md): inactive means the routes are absent
(404) and ``/capabilities`` reports it. When active, endpoints still guard
their own downstream configuration with 503s.
"""

from fastapi.testclient import TestClient

import app.main as app_main
from app.core.config import Settings
from app.core.deps import get_settings


def _active_client() -> TestClient:
    """An API app with the examples module active but nothing else configured."""
    api_app = app_main.build_api_app(Settings(enable_databricks_integrations=True))
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        enable_databricks_integrations=True
    )
    return TestClient(api_app)


def test_examples_routes_absent_when_module_inactive():
    with TestClient(app_main.app) as client:
        response = client.post("/api/examples/embed", json={"title": "hello"})
    assert response.status_code == 404


def test_capabilities_reports_module_state():
    with TestClient(app_main.app) as client:
        response = client.get("/api/capabilities")
    assert response.status_code == 200
    modules = {m["name"]: m["active"] for m in response.json()["modules"]}
    assert modules["examples"] is False
    assert modules["knowledge-diy"] is False


def test_serving_returns_503_when_endpoint_not_configured():
    response = _active_client().post(
        "/examples/serving", json=[{"id": "1", "data": "hello"}]
    )
    assert response.status_code == 503


def test_job_returns_503_when_job_id_not_configured():
    response = _active_client().post("/examples/job", json={"payload": "x"})
    assert response.status_code == 503


def test_agent_ask_returns_503_when_agent_not_configured():
    response = _active_client().post(
        "/examples/agent/ask",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 503
