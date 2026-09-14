"""The exported stream contract lists every event the backend can emit."""

from __future__ import annotations

from typing import get_args

import app.main as app_main
from app.api.chat_stream_controller import STREAMING_EVENT_MODELS


def _api_app():
    for route in app_main.app.routes:
        if getattr(route, "path", None) == "/api":
            return route.app
    raise AssertionError("Mounted /api app not found")


def test_stream_event_mapping_covers_every_event_model():
    schema = _api_app().openapi()
    mapping = schema["components"]["schemas"]["ChatStreamEvent"]["discriminator"][
        "mapping"
    ]
    expected = {
        get_args(m.model_fields["type"].annotation)[0] for m in STREAMING_EVENT_MODELS
    }
    assert set(mapping) == expected
    assert {"tool-result", "heartbeat"} <= expected
