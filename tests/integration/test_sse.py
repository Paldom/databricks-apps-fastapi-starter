from __future__ import annotations

from tests.conftest import test_client  # noqa: F401


def test_sse_stream_returns_event_stream(test_client):  # noqa: F811
    with test_client.stream("GET", "/api/stream/sse") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_bytes())

    text = body.decode()
    assert "event: message" in text
    assert "data: chunk-0" in text
    assert "data: chunk-1" in text
    assert "data: chunk-2" in text
    assert "event: done" in text
    assert "data: complete" in text


def test_sse_stream_custom_count(test_client):  # noqa: F811
    with test_client.stream("GET", "/api/stream/sse?count=2") as response:
        assert response.status_code == 200
        body = b"".join(response.iter_bytes())

    text = body.decode()
    assert "data: chunk-0" in text
    assert "data: chunk-1" in text
    assert "data: chunk-2" not in text
    assert "event: done" in text


def test_sse_stream_rejects_count_over_max(test_client):  # noqa: F811
    response = test_client.get("/api/stream/sse?count=21")
    assert response.status_code == 422
