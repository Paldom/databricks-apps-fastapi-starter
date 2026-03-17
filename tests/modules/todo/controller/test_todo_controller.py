import pytest
from unittest.mock import AsyncMock
from app.api.todo_controller import list_todos, create_todo, get_todo
from app.models.todo_dto import TodoCreate


@pytest.mark.asyncio
async def test_list_todos_calls_service(mock_todo_service, monkeypatch):
    mock_todo_service.list = AsyncMock(return_value=["x"])
    monkeypatch.setattr("app.api.todo_controller.paginate", lambda x: x)
    result = await list_todos(service=mock_todo_service)
    assert result == ["x"]
    mock_todo_service.list.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_todo_calls_service(mock_todo_service):
    mock_todo_service.create = AsyncMock(return_value="x")
    payload = TodoCreate(title="t")
    result = await create_todo(payload, service=mock_todo_service)
    assert result == "x"
    mock_todo_service.create.assert_awaited_once_with(payload)


@pytest.mark.asyncio
async def test_get_todo_calls_service(mock_todo_service):
    mock_todo_service.get = AsyncMock(return_value="x")
    result = await get_todo("1", service=mock_todo_service)
    assert result == "x"
    mock_todo_service.get.assert_awaited_once_with("1")
