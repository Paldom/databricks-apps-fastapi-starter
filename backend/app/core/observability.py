"""Thin observability helpers wrapping OpenTelemetry APIs.

All functions are safe to call when OTel is not configured -- they degrade to
no-ops.  This module must NOT import or instantiate any provider, exporter, or
SDK configurator.  That is handled by ``opentelemetry-instrument``.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import trace
from opentelemetry.trace import StatusCode

_TRACER: trace.Tracer | None = None


def get_tracer(name: str = "app") -> trace.Tracer:
    """Return a Tracer for the given instrumentation scope."""
    global _TRACER
    if name == "app" and _TRACER is not None:
        return _TRACER
    tracer = trace.get_tracer(name)
    if name == "app":
        _TRACER = tracer
    return tracer


def tag_exception(span: trace.Span, exc: Exception) -> None:
    """Record an exception on a span and set ERROR status."""
    span.set_status(StatusCode.ERROR, str(exc))
    span.record_exception(exc)


def safe_attr(value: Any) -> str | int | float | bool:
    """Coerce a value to a safe, low-cardinality span attribute.

    - None  -> ""
    - bool  -> bool
    - int/float -> numeric
    - Everything else -> str, truncated to 256 chars
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    s = str(value)
    return s[:256] if len(s) > 256 else s
