"""Keyset cursors: (timestamp, id) encoded as one opaque string.

Ordering by a timestamp alone skips or repeats rows with equal timestamps, so every
list orders by (timestamp, id) and the cursor carries both.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime

from app.core.errors import BadRequestError


def encode_cursor(timestamp: datetime, row_id: uuid.UUID | str) -> str:
    raw = f"{timestamp.isoformat()}|{row_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        stamp, row_id = base64.urlsafe_b64decode(padded).decode().split("|", 1)
        return datetime.fromisoformat(stamp), row_id
    except (ValueError, UnicodeDecodeError) as exc:
        raise BadRequestError("Invalid cursor") from exc
