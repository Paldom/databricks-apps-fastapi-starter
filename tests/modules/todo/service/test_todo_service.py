import pytest
from unittest.mock import MagicMock

from app.services.todo_service import TodoService
from app.models.todo_dto import TodoRead, TodoCreate, TodoUpdate
from app.models.user_dto import CurrentUser


def _make_dto(**overrides):
    defaults = dict(
        id="00000000-0000-0000-0000-000000000001",
        title="t",
        completed=False,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        created_by="u1",
        updated_by="u1",
    )
    defaults.update(overrides)
    return TodoRead(**defaults)


@pytest.mark.asyncio
async def test_list_calls_query_repo(mock_query_repo, mock_command_repo):
    user = CurrentUser(id="u1")
    service = TodoService(mock_query_repo, mock_command_repo, user, MagicMock())
    dto = _make_dto()
    mock_query_repo.list.return_value = [dto]

    result = await service.list()

    mock_query_repo.list.assert_awaited_once()
    assert result == [dto]


@pytest.mark.asyncio
async def test_get_calls_query_repo(mock_query_repo, mock_command_repo):
    user = CurrentUser(id="u1")
    service = TodoService(mock_query_repo, mock_command_repo, user, MagicMock())
    dto = _make_dto()
    mock_query_repo.get.return_value = dto

    result = await service.get("x")

    mock_query_repo.get.assert_awaited_once_with("x")
    assert result == dto


@pytest.mark.asyncio
async def test_get_raises_when_not_found(mock_query_repo, mock_command_repo):
    user = CurrentUser(id="u1")
    service = TodoService(mock_query_repo, mock_command_repo, user, MagicMock())
    mock_query_repo.get.return_value = None
    with pytest.raises(Exception):
        await service.get("x")


@pytest.mark.asyncio
async def test_create_calls_command_repo(
    mock_query_repo, mock_command_repo, monkeypatch
):
    user = CurrentUser(id="u1")
    service = TodoService(mock_query_repo, mock_command_repo, user, MagicMock())
    todo = MagicMock()
    mock_command_repo.create.return_value = todo
    dto = _make_dto()
    monkeypatch.setattr("app.services.todo_service.to_dto", MagicMock(return_value=dto))

    result = await service.create(TodoCreate(title="t"))

    mock_command_repo.create.assert_awaited_once_with(title="t")
    assert result == dto


@pytest.mark.asyncio
async def test_update_fetches_mutates_and_persists(
    mock_query_repo, mock_command_repo, monkeypatch
):
    user = CurrentUser(id="u1")
    service = TodoService(mock_query_repo, mock_command_repo, user, MagicMock())
    todo = MagicMock(created_by="u1")
    mock_command_repo.get_for_update.return_value = todo
    mock_command_repo.update.return_value = todo
    dto = _make_dto(title="n", completed=True)
    monkeypatch.setattr("app.services.todo_service.to_dto", MagicMock(return_value=dto))

    data = TodoUpdate(title="n", completed=True)
    result = await service.update("x", data)

    mock_command_repo.get_for_update.assert_awaited_once_with("x")
    assert todo.title == "n"
    assert todo.completed is True
    assert todo.updated_by == "u1"
    mock_command_repo.update.assert_awaited_once_with(todo)
    assert result == dto


@pytest.mark.asyncio
async def test_update_raises_when_not_found(mock_query_repo, mock_command_repo):
    user = CurrentUser(id="u1")
    service = TodoService(mock_query_repo, mock_command_repo, user, MagicMock())
    mock_command_repo.get_for_update.return_value = None

    with pytest.raises(Exception):
        await service.update("x", TodoUpdate(title="n"))


@pytest.mark.asyncio
async def test_delete_calls_command_repo(mock_query_repo, mock_command_repo):
    user = CurrentUser(id="u1")
    service = TodoService(mock_query_repo, mock_command_repo, user, MagicMock())
    todo = MagicMock(created_by="u1")
    mock_command_repo.get_for_update.return_value = todo

    await service.delete("x")

    mock_command_repo.get_for_update.assert_awaited_once_with("x")
    mock_command_repo.delete.assert_awaited_once_with(todo)


@pytest.mark.asyncio
async def test_delete_raises_when_not_found(mock_query_repo, mock_command_repo):
    user = CurrentUser(id="u1")
    service = TodoService(mock_query_repo, mock_command_repo, user, MagicMock())
    mock_command_repo.get_for_update.return_value = None

    with pytest.raises(Exception):
        await service.delete("x")
