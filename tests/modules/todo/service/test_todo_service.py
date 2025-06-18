import pytest
from unittest.mock import AsyncMock, MagicMock

from modules.todo.services import TodoService
from modules.todo.schemas import TodoRead, TodoCreate, TodoUpdate
from modules.todo import mappers
from core.auth import UserInfo


@pytest.mark.asyncio
async def test_list_calls_repo_with_user(mock_repo, monkeypatch):
    user = UserInfo(user_id="u1")
    service = TodoService(mock_repo, user, MagicMock())
    todo = MagicMock()
    mock_repo.list.return_value = [todo]
    dto = TodoRead(id="00000000-0000-0000-0000-000000000001", title="t", completed=False, created_at="2024-01-01T00:00:00Z", updated_at="2024-01-01T00:00:00Z", created_by="u1", updated_by="u1")
    mappers_to_dto = MagicMock(return_value=dto)
    monkeypatch.setattr(mappers, "to_dto", mappers_to_dto)
    monkeypatch.setattr("modules.todo.services.to_dto", mappers_to_dto)
    result = await service.list()

    mock_repo.list.assert_awaited_once_with(created_by="u1")
    assert result == [mappers_to_dto.return_value]


@pytest.mark.asyncio
async def test_create_calls_repo(mock_repo, monkeypatch):
    user = UserInfo(user_id="u1")
    service = TodoService(mock_repo, user, MagicMock())
    todo = MagicMock()
    mock_repo.create.return_value = todo
    dto = TodoRead(id="00000000-0000-0000-0000-000000000002", title="t", completed=False, created_at="2024-01-01T00:00:00Z", updated_at="2024-01-01T00:00:00Z", created_by="u1", updated_by="u1")
    mappers_to_dto = MagicMock(return_value=dto)
    monkeypatch.setattr(mappers, "to_dto", mappers_to_dto)
    monkeypatch.setattr("modules.todo.services.to_dto", mappers_to_dto)
    result = await service.create(TodoCreate(title="t"))
    mock_repo.create.assert_awaited_once_with(title="t", user="u1")
    assert result == mappers_to_dto.return_value


@pytest.mark.asyncio
async def test_get_raises_when_not_found(mock_repo):
    user = UserInfo(user_id="u1")
    service = TodoService(mock_repo, user, MagicMock())
    mock_repo.get.return_value = None
    with pytest.raises(Exception):
        await service.get("x")


@pytest.mark.asyncio
async def test_update_updates_fields(mock_repo, monkeypatch):
    user = UserInfo(user_id="u1")
    service = TodoService(mock_repo, user, MagicMock())
    todo = MagicMock(created_by="u1")
    mock_repo.get.return_value = todo
    mock_repo.update.return_value = todo
    dto = TodoRead(id="00000000-0000-0000-0000-000000000003", title="n", completed=True, created_at="2024-01-01T00:00:00Z", updated_at="2024-01-01T00:00:00Z", created_by="u1", updated_by="u1")
    mappers_to_dto = MagicMock(return_value=dto)
    monkeypatch.setattr(mappers, "to_dto", mappers_to_dto)
    monkeypatch.setattr("modules.todo.services.to_dto", mappers_to_dto)
    data = TodoUpdate(title="n", completed=True)
    result = await service.update("x", data)
    assert todo.title == "n"
    assert todo.completed
    mock_repo.update.assert_awaited_once_with(todo)
    assert result == mappers_to_dto.return_value


@pytest.mark.asyncio
async def test_delete_calls_repo(mock_repo):
    user = UserInfo(user_id="u1")
    service = TodoService(mock_repo, user, MagicMock())
    todo = MagicMock(created_by="u1")
    mock_repo.get.return_value = todo
    await service.delete("x")
    mock_repo.delete.assert_awaited_once_with(todo)

