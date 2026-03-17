import asyncio
import logging
from typing import Any, Callable

from app.core.errors import ExternalServiceError

logger = logging.getLogger(__name__)


async def run_sync(
    func: Callable[..., Any],
    *args: Any,
    error_cls: type[ExternalServiceError] = ExternalServiceError,
    timeout: float | None = None,
    **kwargs: Any,
) -> Any:
    """Run a synchronous SDK call in a thread, wrapping errors.

    All adapter-layer sync calls should use this helper to ensure
    consistent error mapping and thread offloading.

    When *timeout* is provided the coroutine is cancelled after the given
    number of seconds.  Note that the underlying thread continues running
    (Python limitation) but the async caller is unblocked.
    """
    try:
        coro = asyncio.to_thread(func, *args, **kwargs)
        if timeout is not None:
            return await asyncio.wait_for(coro, timeout=timeout)
        return await coro
    except asyncio.TimeoutError:
        detail = f"{getattr(func, '__qualname__', str(func))} timed out after {timeout}s"
        logger.warning("Timeout | %s", detail)
        raise error_cls(detail) from None
    except error_cls:
        raise
    except Exception as exc:
        raise error_cls(str(exc), cause=exc) from exc
