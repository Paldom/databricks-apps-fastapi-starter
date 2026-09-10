import logging
from logging import Filter, Logger, LogRecord

from app.core.context import log_fields

_logger = logging.getLogger("app")
_CONFIGURED = False

# Under opentelemetry-instrument the line format comes from OTEL_PYTHON_LOG_FORMAT (set in
# the bundle) with the same fields; this one is for local runs.
_LOCAL_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s "
    "[request_id=%(request_id)s session_id=%(session_id)s user_id=%(user_id)s] "
    "[trace=%(otelTraceID)s span=%(otelSpanID)s]: "
    "%(message)s"
)

_FORMAT_DEFAULTS = {
    "request_id": "-",
    "session_id": "-",
    "user_id": "-",
    "otelTraceID": "0",
    "otelSpanID": "0",
}


class ContextFilter(Filter):
    """Stamp request_id, session_id and user_id on every record that reaches a handler."""

    def filter(self, record: LogRecord) -> bool:
        from app.middlewares.request_context import get_request_id

        fields = log_fields.get()
        record.request_id = get_request_id() or "-"  # type: ignore[attr-defined]
        record.session_id = fields.get("session_id") or "-"  # type: ignore[attr-defined]
        record.user_id = fields.get("user_id") or "-"  # type: ignore[attr-defined]
        return True


def setup_logging(level: str) -> None:
    """Configure root logging for the application (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    if not root.handlers:  # local dev; under OTel the instrumentation installed one
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(_LOCAL_FORMAT, defaults=_FORMAT_DEFAULTS)
        )
        root.addHandler(handler)

    root.setLevel(level)
    # Logger-level filters only see the logger's own records; handler filters see all.
    for existing in root.handlers:
        existing.addFilter(ContextFilter())
    _CONFIGURED = True


def get_logger() -> Logger:
    """Return application logger instance."""
    return _logger
