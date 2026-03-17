import pytest
from unittest.mock import AsyncMock, MagicMock
from app.api.todo_controller import list_todos, create_todo, get_todo
from app.models.todo_dto import TodoCreate, TodoRead


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
async def test_list_todos_calls_service(mock_todo_service, monkeypatch):
    mock_todo_service.list = AsyncMock(return_value=["x"])
    page = MagicMock(model_dump=MagicMock(return_value={"items": ["x"]}))
    monkeypatch.setattr("app.api.todo_controller.paginate", lambda x: page)
    # Provide minimal request/response mocks
    request = MagicMock()
    request.headers = {}
    response = MagicMock()
    response.headers = {}
    monkeypatch.setattr("app.api.todo_controller.build_etag", lambda x: '"abc"')
    result = await list_todos(request=request, response=response, service=mock_todo_service)
    assert result is page
    mock_todo_service.list.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_todo_calls_service(mock_todo_service):
    mock_todo_service.create = AsyncMock(return_value="x")
    payload = TodoCreate(title="t")
    result = await create_todo(payload, service=mock_todo_service)
    assert result == "x"
    mock_todo_service.create.assert_awaited_once_with(payload)


@pytest.mark.asyncio
async def test_get_todo_calls_service(mock_todo_service, monkeypatch):
    dto = _make_dto()
    mock_todo_service.get = AsyncMock(return_value=dto)
    request = MagicMock()
    request.headers = {}
    response = MagicMock()
    response.headers = {}
    result = await get_todo("1", request=request, response=response, service=mock_todo_service)
    assert result == dto
    mock_todo_service.get.assert_awaited_once_with("1")


@pytest.mark.asyncio
async def test_get_todo_returns_etag_header(mock_todo_service):
    dto = _make_dto()
    mock_todo_service.get = AsyncMock(return_value=dto)
    request = MagicMock()
    request.headers = {}
    response = MagicMock()
    response.headers = {}
    await get_todo("1", request=request, response=response, service=mock_todo_service)
    assert "ETag" in response.headers
    assert "Cache-Control" in response.headers
    assert response.headers["Cache-Control"] == "private, no-cache"


@pytest.mark.asyncio
async def test_get_todo_returns_304_when_etag_matches(mock_todo_service):
    from app.core.http_cache import build_etag

    dto = _make_dto()
    mock_todo_service.get = AsyncMock(return_value=dto)
    etag = build_etag(dto.model_dump(mode="json"))
    request = MagicMock()
    request.headers = {"if-none-match": etag}
    response = MagicMock()
    response.headers = {}
    result = await get_todo("1", request=request, response=response, service=mock_todo_service)
    assert result.status_code == 304
    assert result.body == b""


@pytest.mark.asyncio
async def test_list_todos_returns_etag_header(mock_todo_service, monkeypatch):
    dto = _make_dto()
    mock_todo_service.list = AsyncMock(return_value=[dto])
    monkeypatch.setattr("app.api.todo_controller.paginate", lambda x: MagicMock(
        model_dump=MagicMock(return_value={"items": [dto.model_dump(mode="json")]}),
    ))
    request = MagicMock()
    request.headers = {}
    response = MagicMock()
    response.headers = {}
    await list_todos(request=request, response=response, service=mock_todo_service)
    assert "ETag" in response.headers
    assert "Cache-Control" in response.headers


@pytest.mark.asyncio
async def test_list_todos_returns_304_when_etag_matches(mock_todo_service, monkeypatch):
    from app.core.http_cache import build_etag

    dto = _make_dto()
    mock_todo_service.list = AsyncMock(return_value=[dto])
    page_data = {"items": [dto.model_dump(mode="json")]}
    page_mock = MagicMock(model_dump=MagicMock(return_value=page_data))
    monkeypatch.setattr("app.api.todo_controller.paginate", lambda x: page_mock)

    etag = build_etag(page_data)
    request = MagicMock()
    request.headers = {"if-none-match": etag}
    response = MagicMock()
    response.headers = {}
    result = await list_todos(request=request, response=response, service=mock_todo_service)
    assert result.status_code == 304
    assert result.body == b""
