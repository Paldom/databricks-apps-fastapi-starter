"""Every log line that reaches a handler carries request, session and user ids."""

from __future__ import annotations

import logging

from app.core.context import log_fields
from app.core.logging import ContextFilter


def test_handler_filter_stamps_turn_identity(caplog):
    handler = caplog.handler
    handler.addFilter(ContextFilter())
    try:
        token = log_fields.set({"session_id": "chat-1", "user_id": "user-a"})
        try:
            logging.getLogger("app.some.module").warning("turn started")
        finally:
            log_fields.reset(token)
        logging.getLogger("third.party").info("outside a turn")
    finally:
        handler.removeFilter(handler.filters[-1])

    inside, outside = caplog.records[-2:]
    assert (inside.session_id, inside.user_id) == ("chat-1", "user-a")  # type: ignore[attr-defined]
    assert (outside.session_id, outside.user_id) == ("-", "-")  # type: ignore[attr-defined]
    assert inside.request_id == "-"  # type: ignore[attr-defined]
