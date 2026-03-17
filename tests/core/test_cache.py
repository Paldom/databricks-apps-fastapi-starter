import importlib.util

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.cache import NullCache, AiocacheCache, build_cache


HAS_AIOCACHE = importlib.util.find_spec("aiocache") is not None


# ---------------------------------------------------------------------------
# NullCache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_null_cache_get_returns_none():
    cache = NullCache()
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_null_cache_set_does_not_raise():
    cache = NullCache()
    await cache.set("k", "v", ttl=10)


@pytest.mark.asyncio
async def test_null_cache_delete_does_not_raise():
    cache = NullCache()
    await cache.delete("k")


@pytest.mark.asyncio
async def test_null_cache_increment_returns_zero():
    cache = NullCache()
    assert await cache.increment("k") == 0


@pytest.mark.asyncio
async def test_null_cache_close_does_not_raise():
    cache = NullCache()
    await cache.close()


# ---------------------------------------------------------------------------
# AiocacheCache — delegation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aiocache_get_delegates():
    backend = AsyncMock()
    backend.get.return_value = "val"
    cache = AiocacheCache(backend)
    assert await cache.get("k") == "val"
    backend.get.assert_awaited_once_with("k")


@pytest.mark.asyncio
async def test_aiocache_set_delegates():
    backend = AsyncMock()
    cache = AiocacheCache(backend)
    await cache.set("k", "v", ttl=30)
    backend.set.assert_awaited_once_with("k", "v", ttl=30)


@pytest.mark.asyncio
async def test_aiocache_delete_delegates():
    backend = AsyncMock()
    cache = AiocacheCache(backend)
    await cache.delete("k")
    backend.delete.assert_awaited_once_with("k")


@pytest.mark.asyncio
async def test_aiocache_increment_does_get_set():
    backend = AsyncMock()
    backend.get.return_value = 5
    cache = AiocacheCache(backend)
    result = await cache.increment("k")
    assert result == 6
    backend.get.assert_awaited_once_with("k")
    backend.set.assert_awaited_once_with("k", 6)


@pytest.mark.asyncio
async def test_aiocache_increment_initialises_from_none():
    backend = AsyncMock()
    backend.get.return_value = None
    cache = AiocacheCache(backend)
    result = await cache.increment("k")
    assert result == 1
    backend.set.assert_awaited_once_with("k", 1)


@pytest.mark.asyncio
async def test_aiocache_increment_with_delta():
    backend = AsyncMock()
    backend.get.return_value = 3
    cache = AiocacheCache(backend)
    result = await cache.increment("k", delta=5)
    assert result == 8


# ---------------------------------------------------------------------------
# AiocacheCache — graceful failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aiocache_get_swallows_exception():
    backend = AsyncMock()
    backend.get.side_effect = RuntimeError("boom")
    cache = AiocacheCache(backend)
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_aiocache_set_swallows_exception():
    backend = AsyncMock()
    backend.set.side_effect = RuntimeError("boom")
    cache = AiocacheCache(backend)
    await cache.set("k", "v")  # should not raise


@pytest.mark.asyncio
async def test_aiocache_delete_swallows_exception():
    backend = AsyncMock()
    backend.delete.side_effect = RuntimeError("boom")
    cache = AiocacheCache(backend)
    await cache.delete("k")  # should not raise


@pytest.mark.asyncio
async def test_aiocache_increment_swallows_exception():
    backend = AsyncMock()
    backend.get.side_effect = RuntimeError("boom")
    cache = AiocacheCache(backend)
    assert await cache.increment("k") == 0


@pytest.mark.asyncio
async def test_aiocache_close_swallows_exception():
    backend = AsyncMock()
    backend.close.side_effect = RuntimeError("boom")
    cache = AiocacheCache(backend)
    await cache.close()  # should not raise


# ---------------------------------------------------------------------------
# build_cache
# ---------------------------------------------------------------------------


def test_build_cache_disabled_returns_null_cache():
    s = MagicMock(cache_enabled=False)
    cache = build_cache(s)
    assert isinstance(cache, NullCache)


def test_build_cache_memory_returns_aiocache_cache():
    s = MagicMock(
        cache_enabled=True,
        cache_backend="memory",
        cache_namespace="test",
    )
    cache = build_cache(s)
    expected_type = AiocacheCache if HAS_AIOCACHE else NullCache
    assert isinstance(cache, expected_type)


def test_build_cache_redis_returns_aiocache_cache(monkeypatch):
    s = MagicMock(
        cache_enabled=True,
        cache_backend="redis",
        cache_namespace="test",
        cache_redis_endpoint="localhost",
        cache_redis_port=6379,
        cache_redis_db=0,
        cache_redis_password=None,
    )
    # Don't actually connect to Redis — just verify the code path
    cache = build_cache(s)
    expected_type = AiocacheCache if HAS_AIOCACHE else NullCache
    assert isinstance(cache, expected_type)


def test_build_cache_failure_returns_null_cache(monkeypatch):
    """If aiocache import fails, gracefully fall back to NullCache."""
    import app.core.cache as cache_mod

    original_build = cache_mod.build_cache

    def patched_build(settings):
        # Force an import error by temporarily breaking the import
        import builtins

        real_import = builtins.__import__

        def broken_import(name, *args, **kwargs):
            if "aiocache" in name:
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", broken_import)
        try:
            return original_build(settings)
        finally:
            monkeypatch.setattr(builtins, "__import__", real_import)

    s = MagicMock(cache_enabled=True, cache_backend="memory", cache_namespace="test")
    result = patched_build(s)
    assert isinstance(result, NullCache)
