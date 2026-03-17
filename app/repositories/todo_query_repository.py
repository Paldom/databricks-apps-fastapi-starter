"""Read-only repository for Todo entities with cache-aside pattern.

Returns :class:`TodoRead` DTOs — never ORM entities.  All queries are
user-scoped (``WHERE created_by = user_id``).
"""

from __future__ import annotations

from logging import Logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache
from app.models.todo_dto import TodoRead, to_dto
from app.models.todo_model import Todo
from app.repositories.todo_cache_keys import (
    detail_key,
    list_data_key,
    list_version_key,
)


class TodoQueryRepository:

    def __init__(
        self,
        session: AsyncSession,
        cache: Cache,
        user_id: str,
        logger: Logger,
        *,
        detail_ttl: int = 120,
        list_ttl: int = 60,
    ):
        self.session = session
        self.cache = cache
        self.user_id = user_id
        self.logger = logger
        self.detail_ttl = detail_ttl
        self.list_ttl = list_ttl

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list(self) -> list[TodoRead]:
        """Return all todos for the current user (cache-aside)."""
        # 1. Resolve current list version
        version = await self.cache.get(list_version_key(self.user_id))
        version = version or 0

        # 2. Try versioned list cache
        lk = list_data_key(self.user_id, version)
        cached = await self.cache.get(lk)
        if cached is not None:
            self.logger.debug("cache HIT for list (version=%s)", version)
            return [TodoRead.model_validate(item) for item in cached]

        # 3. Cache miss — query DB
        self.logger.debug("cache MISS for list (version=%s)", version)
        stmt = (
            select(Todo)
            .where(Todo.created_by == self.user_id)
            .order_by(Todo.created_at.desc())
        )
        entities = (await self.session.scalars(stmt)).all()
        dtos = [to_dto(e) for e in entities]

        # 4. Serialize and cache
        serialized = [d.model_dump(mode="json") for d in dtos]
        await self.cache.set(lk, serialized, ttl=self.list_ttl)

        return dtos

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    async def get(self, todo_id: str) -> TodoRead | None:
        """Return a single todo for the current user, or ``None``."""
        # 1. Try detail cache
        dk = detail_key(self.user_id, todo_id)
        cached = await self.cache.get(dk)
        if cached is not None:
            self.logger.debug("cache HIT for todo %s", todo_id)
            return TodoRead.model_validate(cached)

        # 2. Cache miss — query DB with user scope
        self.logger.debug("cache MISS for todo %s", todo_id)
        stmt = select(Todo).where(
            Todo.id == todo_id, Todo.created_by == self.user_id
        )
        entity = (await self.session.scalars(stmt)).first()
        if entity is None:
            return None

        dto = to_dto(entity)

        # 3. Cache the result
        await self.cache.set(dk, dto.model_dump(mode="json"), ttl=self.detail_ttl)

        return dto
