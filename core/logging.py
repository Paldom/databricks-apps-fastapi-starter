import logging
from logging import Logger

_logger = logging.getLogger("app")


def setup_logging(level: str) -> None:
    """Configure root logging for the application."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _logger.debug("Logging initialized at level %s", level)


def get_logger() -> Logger:
    """Return application logger instance."""
    return _logger

