"""Reusable cache infrastructure.

Provides a ``Cache`` protocol that the rest of the application programs
against, a ``NullCache`` no-op implementation (disabled cache / fallback),
an ``AiocacheCache`` adapter wrapping *aiocache* backends, and a
``build_cache`` factory that selects memory vs Redis from settings.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Cache(Protocol):
    """Application cache protocol.  All methods are async and never raise."""

    async def get(self, key: str) -> Any | None: ...

    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def increment(self, key: str, delta: int = 1) -> int: ...

    async def close(self) -> None: ...


# ---------------------------------------------------------------------------
# NullCache (disabled / fallback)
# ---------------------------------------------------------------------------


class NullCache:
    """No-op cache that silently discards everything."""

    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass

    async def increment(self, key: str, delta: int = 1) -> int:
        return 0

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# AiocacheCache adapter
# ---------------------------------------------------------------------------


class AiocacheCache:
    """Adapter wrapping an *aiocache* backend.

    Every public method swallows exceptions and logs a warning so that
    cache failures never break business requests.
    """

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    async def get(self, key: str) -> Any | None:
        try:
            return await self._backend.get(key)
        except Exception:
            logger.warning("cache.get failed for key=%s", key, exc_info=True)
            return None

    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        try:
            await self._backend.set(key, value, ttl=ttl)
        except Exception:
            logger.warning("cache.set failed for key=%s", key, exc_info=True)

    async def delete(self, key: str) -> None:
        try:
            await self._backend.delete(key)
        except Exception:
            logger.warning("cache.delete failed for key=%s", key, exc_info=True)

    async def increment(self, key: str, delta: int = 1) -> int:
        """Increment a counter key.  Uses get-then-set (not atomic)."""
        try:
            current = await self._backend.get(key)
            new_val = (current or 0) + delta
            await self._backend.set(key, new_val)
            return new_val
        except Exception:
            logger.warning("cache.increment failed for key=%s", key, exc_info=True)
            return 0

    async def close(self) -> None:
        try:
            await self._backend.close()
        except Exception:
            logger.warning("cache.close failed", exc_info=True)


# ---------------------------------------------------------------------------
# Builder / factory
# ---------------------------------------------------------------------------


def build_cache(settings: Any) -> Cache:
    """Build a :class:`Cache` instance from application settings.

    Returns :class:`NullCache` when caching is disabled or on any
    construction failure.
    """
    if not getattr(settings, "cache_enabled", False):
        logger.info("Cache disabled by configuration")
        return NullCache()

    try:
        from aiocache.serializers import JsonSerializer

        if settings.cache_backend == "redis":
            from aiocache import RedisCache

            backend = RedisCache(
                endpoint=settings.cache_redis_endpoint,
                port=settings.cache_redis_port,
                password=settings.cache_redis_password or None,
                db=settings.cache_redis_db,
                namespace=settings.cache_namespace,
                serializer=JsonSerializer(),
            )
        else:
            from aiocache import SimpleMemoryCache

            backend = SimpleMemoryCache(
                namespace=settings.cache_namespace,
                serializer=JsonSerializer(),
            )

        logger.info("Cache initialized: backend=%s", settings.cache_backend)
        return AiocacheCache(backend)

    except Exception:
        logger.error(
            "Failed to build cache, falling back to NullCache", exc_info=True
        )
        return NullCache()
