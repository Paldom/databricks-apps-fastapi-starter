"""Write repository for Todo entities with explicit cache invalidation.

Performs mutations, flushes (never commits), then invalidates relevant
cache keys.  Cache invalidation happens after ``flush()`` — see the
plan's "Notable Trade-offs" section for the timing rationale.
"""

from __future__ import annotations

from logging import Logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache
from app.models.todo_dto import to_dto
from app.models.todo_model import Todo
from app.repositories.todo_cache_keys import detail_key, list_version_key


class TodoCommandRepository:

    def __init__(
        self,
        session: AsyncSession,
        cache: Cache,
        user_id: str,
        logger: Logger,
        *,
        detail_ttl: int = 120,
    ):
        self.session = session
        self.cache = cache
        self.user_id = user_id
        self.logger = logger
        self.detail_ttl = detail_ttl

    # ------------------------------------------------------------------
    # Read (mutable entity access for update/delete flows)
    # ------------------------------------------------------------------

    async def get_for_update(self, todo_id: str) -> Todo | None:
        """Fetch a mutable entity for the current user, or ``None``."""
        stmt = select(Todo).where(
            Todo.id == todo_id, Todo.created_by == self.user_id
        )
        return (await self.session.scalars(stmt)).first()

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(self, title: str) -> Todo:
        todo = Todo(title=title, created_by=self.user_id, updated_by=self.user_id)
        self.session.add(todo)
        await self.session.flush()
        await self.session.refresh(todo)

        # Warm detail cache
        dto = to_dto(todo)
        dk = detail_key(self.user_id, str(dto.id))
        await self.cache.set(dk, dto.model_dump(mode="json"), ttl=self.detail_ttl)

        # Bump list version so stale list snapshots are bypassed
        await self.cache.increment(list_version_key(self.user_id))

        self.logger.debug("Created todo %s, cache invalidated", dto.id)
        return todo

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(self, todo: Todo) -> Todo:
        """Flush the mutated entity, refresh it, and invalidate cache."""
        await self.session.flush()
        await self.session.refresh(todo)

        # Overwrite detail cache with fresh data
        dto = to_dto(todo)
        dk = detail_key(self.user_id, str(dto.id))
        await self.cache.set(dk, dto.model_dump(mode="json"), ttl=self.detail_ttl)

        # Bump list version
        await self.cache.increment(list_version_key(self.user_id))

        self.logger.debug("Updated todo %s, cache invalidated", dto.id)
        return todo

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, todo: Todo) -> None:
        """Delete entity, flush, and invalidate cache."""
        todo_id = str(todo.id)
        # NOTE: if ownership transfer is ever supported, both old and new
        # owner list versions must be bumped here.

        await self.session.delete(todo)
        await self.session.flush()

        # Remove detail cache entry
        await self.cache.delete(detail_key(self.user_id, todo_id))

        # Bump list version
        await self.cache.increment(list_version_key(self.user_id))

        self.logger.debug("Deleted todo %s, cache invalidated", todo_id)
