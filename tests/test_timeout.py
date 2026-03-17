import asyncio
import time

import pytest

from app.core.databricks._async_bridge import run_sync
from app.core.errors import ExternalServiceError


def _slow_function():
    time.sleep(5)
    return "done"


def _fast_function():
    return "fast"


@pytest.mark.asyncio
async def test_run_sync_timeout():
    """run_sync should raise error_cls when the timeout expires."""
    with pytest.raises(ExternalServiceError, match="timed out"):
        await run_sync(_slow_function, timeout=0.1)


@pytest.mark.asyncio
async def test_run_sync_no_timeout():
    """run_sync should succeed for fast calls."""
    result = await run_sync(_fast_function, timeout=5.0)
    assert result == "fast"


@pytest.mark.asyncio
async def test_run_sync_wraps_exceptions():
    """Non-timeout exceptions should be wrapped in error_cls."""

    def _failing():
        raise ValueError("boom")

    with pytest.raises(ExternalServiceError, match="boom"):
        await run_sync(_failing, timeout=5.0)
