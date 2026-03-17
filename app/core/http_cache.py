"""HTTP conditional-request helpers (ETag / If-None-Match)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_etag(payload: Any) -> str:
    """Compute a strong ETag from a JSON-serializable *payload*.

    Uses canonical JSON (sorted keys, compact separators) hashed with
    SHA-256.  Returns a quoted string like ``'"abc123..."'``.
    """
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f'"{digest}"'


def if_none_match_matches(header_value: str | None, etag: str) -> bool:
    """Return ``True`` when any tag in *header_value* matches *etag*.

    Handles:
    - exact quoted match (``"abc"``),
    - multiple comma-separated values (``"abc", "def"``),
    - wildcard (``*``).
    """
    if not header_value:
        return False
    bare_etag = etag.strip('"')
    for part in header_value.split(","):
        tag = part.strip().strip('"')
        if tag == "*" or tag == bare_etag:
            return True
    return False
