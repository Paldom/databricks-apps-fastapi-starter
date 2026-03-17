"""Thin observability helpers wrapping OpenTelemetry APIs.

All functions are safe to call when OTel is not configured -- they degrade to
no-ops.  This module must NOT import or instantiate any provider, exporter, or
SDK configurator.  That is handled by ``opentelemetry-instrument``.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Generator

from opentelemetry import metrics, trace
from opentelemetry.trace import StatusCode

_TRACER: trace.Tracer | None = None
_METER: metrics.Meter | None = None


def get_tracer(name: str = "app") -> trace.Tracer:
    """Return a Tracer for the given instrumentation scope."""
    global _TRACER
    if name == "app" and _TRACER is not None:
        return _TRACER
    tracer = trace.get_tracer(name)
    if name == "app":
        _TRACER = tracer
    return tracer


def get_meter(name: str = "app") -> metrics.Meter:
    """Return a Meter for the given instrumentation scope."""
    global _METER
    if name == "app" and _METER is not None:
        return _METER
    meter = metrics.get_meter(name)
    if name == "app":
        _METER = meter
    return meter


@contextmanager
def start_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Generator[trace.Span, None, None]:
    """Context manager that starts a span with safe attributes."""
    tracer = get_tracer()
    safe_attrs = {k: safe_attr(v) for k, v in (attributes or {}).items()}
    with tracer.start_as_current_span(name, attributes=safe_attrs) as span:
        yield span


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


def record_duration(
    metric_name: str,
    duration_s: float,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Record a duration observation on a histogram (unit: seconds)."""
    meter = get_meter()
    histogram = meter.create_histogram(name=metric_name, unit="s")
    safe_attrs = {k: safe_attr(v) for k, v in (attributes or {}).items()}
    histogram.record(duration_s, attributes=safe_attrs)


def increment_counter(
    metric_name: str,
    amount: int = 1,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Increment a counter metric."""
    meter = get_meter()
    counter = meter.create_counter(name=metric_name)
    safe_attrs = {k: safe_attr(v) for k, v in (attributes or {}).items()}
    counter.add(amount, attributes=safe_attrs)


def timed_scope(metric_name: str) -> "_TimedScope":
    """Return a context manager that measures elapsed time and records it."""
    return _TimedScope(metric_name)


class _TimedScope:
    """Measures wall-clock time and records to a histogram on exit."""

    __slots__ = ("_metric_name", "_start", "_attrs")

    def __init__(self, metric_name: str) -> None:
        self._metric_name = metric_name
        self._start = 0.0
        self._attrs: dict[str, Any] = {}

    def __enter__(self) -> "_TimedScope":
        self._start = time.monotonic()
        return self

    def __exit__(self, *_: object) -> None:
        record_duration(self._metric_name, time.monotonic() - self._start, self._attrs)
