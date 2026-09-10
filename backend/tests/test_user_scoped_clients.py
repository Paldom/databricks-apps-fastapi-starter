"""User-scoped dependencies fail closed under OBO and fall back to the app identity otherwise."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.deps import get_settings, get_user_ai_client, get_user_workspace_client
from app.core.errors import AuthenticationError


def _request(*, enable_obo: bool, user_client=None):
    """Minimal request: settings come through the app's dependency_overrides."""
    settings = MagicMock(enable_obo=enable_obo, openai_timeout_seconds=5)
    app = SimpleNamespace(dependency_overrides={get_settings: lambda: settings})
    return SimpleNamespace(state=SimpleNamespace(w=user_client), app=app)


def test_obo_without_forwarded_token_is_401_not_the_service_principal():
    request = _request(enable_obo=True, user_client=None)
    with pytest.raises(AuthenticationError):
        get_user_workspace_client(request)
    with pytest.raises(AuthenticationError):
        get_user_ai_client(request)


def test_obo_with_forwarded_token_uses_the_user_client():
    user = MagicMock(name="user")
    assert (
        get_user_workspace_client(_request(enable_obo=True, user_client=user)) is user
    )


def test_obo_off_falls_back_to_the_app_identity(monkeypatch):
    request = _request(enable_obo=False, user_client=None)
    monkeypatch.setattr("app.core.deps.get_workspace_client", lambda r: "sp-client")
    monkeypatch.setattr("app.core.deps.get_ai_client", lambda r: "sp-ai-client")
    assert get_user_workspace_client(request) == "sp-client"
    assert get_user_ai_client(request) == "sp-ai-client"
