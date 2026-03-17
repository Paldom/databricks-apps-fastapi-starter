import asyncio
from typing import Any, Callable

from app.core.errors import ExternalServiceError


async def run_sync(
    func: Callable[..., Any],
    *args: Any,
    error_cls: type[ExternalServiceError] = ExternalServiceError,
    **kwargs: Any,
) -> Any:
    """Run a synchronous SDK call in a thread, wrapping errors.

    All adapter-layer sync calls should use this helper to ensure
    consistent error mapping and thread offloading.
    """
    try:
        return await asyncio.to_thread(func, *args, **kwargs)
    except error_cls:
        raise
    except Exception as exc:
        raise error_cls(str(exc), cause=exc) from exc
