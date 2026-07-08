import asyncio
import logging
from collections.abc import Callable
from typing import Any

from app.core.errors import (
    AppError,
    DatabricksAPIError,
    ExternalServiceError,
    RequestTimeoutError,
)

logger = logging.getLogger(__name__)


async def run_sync(
    func: Callable[..., Any],
    *args: Any,
    error_cls: type[ExternalServiceError] = DatabricksAPIError,
    timeout: float | None = None,
    **kwargs: Any,
) -> Any:
    """Run a synchronous SDK call in a thread, mapping errors to the taxonomy.

    All adapter-layer sync calls should use this helper to ensure consistent
    error mapping and thread offloading: SDK/transport failures become
    *error_cls* (default :class:`DatabricksAPIError`, HTTP 502) and timeouts
    become :class:`RequestTimeoutError` (HTTP 504).

    When *timeout* is provided the coroutine is cancelled after the given
    number of seconds.  Note that the underlying thread continues running
    (Python limitation) but the async caller is unblocked.
    """
    try:
        coro = asyncio.to_thread(func, *args, **kwargs)
        if timeout is not None:
            return await asyncio.wait_for(coro, timeout=timeout)
        return await coro
    except TimeoutError:
        detail = (
            f"{getattr(func, '__qualname__', str(func))} timed out after {timeout}s"
        )
        logger.warning("Timeout | %s", detail)
        raise RequestTimeoutError(detail) from None
    except AppError:
        raise
    except Exception as exc:
        raise error_cls(str(exc), cause=exc) from exc
