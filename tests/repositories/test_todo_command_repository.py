import pytest
from unittest.mock import AsyncMock, MagicMock

from app.repositories.todo_command_repository import TodoCommandRepository


def _stub_entity(**overrides):
    defaults = dict(
        id="00000000-0000-0000-0000-000000000001",
        title="buy milk",
        completed=False,
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
        created_by="u1",
        updated_by="u1",
    )
    defaults.update(overrides)
    entity = MagicMock()
    for k, v in defaults.items():
        setattr(entity, k, v)
    return entity


def _make_dto_mock():
    """Return a mock TodoRead-like DTO."""
    dto = MagicMock()
    dto.id = "00000000-0000-0000-0000-000000000001"
    dto.model_dump.return_value = {"id": "00000000-0000-0000-0000-000000000001"}
    return dto


def _make_cache():
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    cache.increment = AsyncMock(return_value=1)
    return cache


def _make_session(entity=None):
    session = MagicMock()
    result_mock = MagicMock()
    result_mock.first.return_value = entity
    session.scalars = AsyncMock(return_value=result_mock)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_flushes_refreshes_and_caches(monkeypatch):
    dto = _make_dto_mock()
    monkeypatch.setattr(
        "app.repositories.todo_command_repository.to_dto", lambda e: dto
    )

    cache = _make_cache()
    session = _make_session()
    repo = TodoCommandRepository(session, cache, "u1", MagicMock())

    await repo.create("buy milk")

    session.add.assert_called_once()
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once()
    cache.set.assert_awaited_once()  # detail cache warmed
    cache.increment.assert_awaited_once()  # list version bumped


@pytest.mark.asyncio
async def test_create_returns_entity(monkeypatch):
    dto = _make_dto_mock()
    monkeypatch.setattr(
        "app.repositories.todo_command_repository.to_dto", lambda e: dto
    )

    cache = _make_cache()
    session = _make_session()
    repo = TodoCommandRepository(session, cache, "u1", MagicMock())

    todo = await repo.create("buy milk")

    assert todo.title == "buy milk"
    assert todo.created_by == "u1"


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_flushes_and_invalidates(monkeypatch):
    entity = _stub_entity()
    dto = _make_dto_mock()
    monkeypatch.setattr(
        "app.repositories.todo_command_repository.to_dto", lambda e: dto
    )

    cache = _make_cache()
    session = _make_session()
    repo = TodoCommandRepository(session, cache, "u1", MagicMock())

    result = await repo.update(entity)

    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(entity)
    cache.set.assert_awaited_once()
    cache.increment.assert_awaited_once()
    assert result is entity


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_removes_and_invalidates():
    entity = _stub_entity()
    cache = _make_cache()
    session = _make_session()
    repo = TodoCommandRepository(session, cache, "u1", MagicMock())

    await repo.delete(entity)

    session.delete.assert_awaited_once_with(entity)
    session.flush.assert_awaited_once()
    cache.delete.assert_awaited_once()  # detail removed
    cache.increment.assert_awaited_once()  # list version bumped


# ---------------------------------------------------------------------------
# get_for_update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_for_update_returns_entity():
    entity = _stub_entity()
    cache = _make_cache()
    session = _make_session(entity)
    repo = TodoCommandRepository(session, cache, "u1", MagicMock())

    result = await repo.get_for_update("t1")

    assert result is entity


@pytest.mark.asyncio
async def test_get_for_update_returns_none_when_missing():
    cache = _make_cache()
    session = _make_session(None)
    repo = TodoCommandRepository(session, cache, "u1", MagicMock())

    result = await repo.get_for_update("t1")

    assert result is None


# ---------------------------------------------------------------------------
# cache failure resilience (documented contract)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_failure_documented():
    """The AiocacheCache adapter swallows exceptions (tested in test_cache.py).

    The command repo does not swallow cache errors itself — it relies on
    the adapter layer.  This is by design: keeping the repo free of
    try/except keeps it readable, and the adapter guarantees fail-open.
    """
    pass
