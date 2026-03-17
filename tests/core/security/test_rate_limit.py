from unittest.mock import MagicMock

import pytest

from app.core.security.rate_limit import _rate_limit_key


def _make_request(*, user=None, real_ip=None, client_host="127.0.0.1"):
    """Build a minimal mock request for rate limit key testing."""
    request = MagicMock()
    request.state.user = user
    request.headers = {}
    if real_ip:
        request.headers["X-Real-Ip"] = real_ip
    client = MagicMock()
    client.host = client_host
    request.client = client
    return request


class TestRateLimitKey:
    def test_keyed_by_user_id(self):
        user = MagicMock()
        user.id = "uid-123"
        user.email = "user@example.com"
        request = _make_request(user=user, real_ip="10.0.0.1")
        assert _rate_limit_key(request) == "user:uid-123"

    def test_keyed_by_email_when_no_id(self):
        user = MagicMock()
        user.id = ""
        user.email = "fallback@example.com"
        request = _make_request(user=user)
        assert _rate_limit_key(request) == "email:fallback@example.com"

    def test_keyed_by_real_ip_when_no_user(self):
        request = _make_request(real_ip="10.0.0.1")
        assert _rate_limit_key(request) == "ip:10.0.0.1"

    def test_keyed_by_client_host_as_fallback(self):
        request = _make_request(client_host="192.168.1.1")
        assert _rate_limit_key(request) == "host:192.168.1.1"

    def test_keyed_unknown_when_no_client(self):
        request = _make_request()
        request.client = None
        assert _rate_limit_key(request) == "host:unknown"
