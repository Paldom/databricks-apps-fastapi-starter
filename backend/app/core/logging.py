import logging
from logging import Filter, Logger, LogRecord

_logger = logging.getLogger("app")
_CONFIGURED = False

_LOCAL_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s "
    "[request_id=%(request_id)s] "
    "[trace=%(otelTraceID)s span=%(otelSpanID)s]: "
    "%(message)s"
)

_FORMAT_DEFAULTS = {
    "request_id": "-",
    "otelTraceID": "0",
    "otelSpanID": "0",
}


class RequestIdFilter(Filter):
    """Inject ``request_id`` from contextvars into every log record."""

    def filter(self, record: LogRecord) -> bool:
        from app.middlewares.request_context import get_request_id

        record.request_id = get_request_id() or "-"  # type: ignore[attr-defined]
        return True


def setup_logging(level: str) -> None:
    """Configure root logging for the application (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()

    # Only add a handler when none exist (local dev without OTel).
    # When running under opentelemetry-instrument, handlers are already
    # configured -- we just set the level and attach the filter.
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(_LOCAL_FORMAT, defaults=_FORMAT_DEFAULTS)
        )
        root.addHandler(handler)

    root.setLevel(level)
    root.addFilter(RequestIdFilter())
    _CONFIGURED = True


def get_logger() -> Logger:
    """Return application logger instance."""
    return _logger
