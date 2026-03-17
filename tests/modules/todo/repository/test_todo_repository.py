import pytest
from unittest.mock import AsyncMock, MagicMock

from app.repositories.todo_repository import TodoRepository


@pytest.mark.asyncio
async def test_list_invokes_session_scalars():
    session = MagicMock()
    result = MagicMock()
    todo = MagicMock()
    result.all.return_value = [todo]
    session.scalars = AsyncMock(return_value=result)

    repo = TodoRepository(session)
    todos = await repo.list()

    session.scalars.assert_called_once()
    assert todos is result.all.return_value


@pytest.mark.asyncio
async def test_get_invokes_session_get():
    session = MagicMock()
    todo = MagicMock()
    session.get = AsyncMock(return_value=todo)
    repo = TodoRepository(session)

    todo = await repo.get("123")

    session.get.assert_called_once()
    assert todo is session.get.return_value


@pytest.mark.asyncio
async def test_create_flushes_and_refreshes():
    session = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()

    repo = TodoRepository(session)
    session.refresh.return_value = MagicMock(title="test")
    todo = await repo.create(title="test", user="u1")

    session.add.assert_called_once()
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once()
    assert todo.title == "test"


@pytest.mark.asyncio
async def test_update_flushes_and_refreshes():
    session = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    repo = TodoRepository(session)
    todo = MagicMock()

    updated = await repo.update(todo)

    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(todo)
    assert updated is todo


@pytest.mark.asyncio
async def test_delete_flushes():
    session = MagicMock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    repo = TodoRepository(session)
    todo = MagicMock()

    await repo.delete(todo)

    session.delete.assert_awaited_once_with(todo)
    session.flush.assert_awaited_once()
