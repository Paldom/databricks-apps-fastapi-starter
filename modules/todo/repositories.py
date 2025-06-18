from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Todo


class TodoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, *, created_by: str | None = None) -> Iterable[Todo]:
        stmt = select(Todo).order_by(Todo.created_at.desc())
        if created_by:
            stmt = stmt.where(Todo.created_by == created_by)
        return (await self.session.scalars(stmt)).all()

    async def get(self, id_: str) -> Todo | None:
        return await self.session.get(Todo, id_)

    async def create(self, title: str, *, user: str) -> Todo:
        todo = Todo(title=title, created_by=user, updated_by=user)
        self.session.add(todo)
        await self.session.commit()
        await self.session.refresh(todo)
        return todo

    async def update(self, todo: Todo) -> Todo:
        await self.session.commit()
        await self.session.refresh(todo)
        return todo

    async def delete(self, todo: Todo) -> None:
        await self.session.delete(todo)
        await self.session.commit()
