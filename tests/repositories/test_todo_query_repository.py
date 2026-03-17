import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.cache import NullCache
from app.models.todo_dto import TodoRead
from app.repositories.todo_query_repository import TodoQueryRepository


def _stub_entity(**overrides):
    """Return a mock ORM entity with TodoRead-compatible attributes."""
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


def _make_cache():
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


def _make_session(entities=None):
    session = MagicMock()
    result_mock = MagicMock()
    result_mock.all.return_value = entities or []
    result_mock.first.return_value = entities[0] if entities else None
    session.scalars = AsyncMock(return_value=result_mock)
    return session


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_cache_miss_queries_db():
    entity = _stub_entity()
    session = _make_session([entity])
    cache = _make_cache()
    repo = TodoQueryRepository(session, cache, "u1", MagicMock())

    result = await repo.list()

    assert len(result) == 1
    assert isinstance(result[0], TodoRead)
    session.scalars.assert_awaited_once()
    cache.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_cache_hit_avoids_db():
    cached_data = [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "title": "buy milk",
            "completed": False,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "created_by": "u1",
            "updated_by": "u1",
        }
    ]
    cache = _make_cache()
    # First call returns version (0), second call returns cached list
    cache.get = AsyncMock(side_effect=[0, cached_data])
    session = _make_session()
    repo = TodoQueryRepository(session, cache, "u1", MagicMock())

    result = await repo.list()

    assert len(result) == 1
    assert isinstance(result[0], TodoRead)
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_uses_versioned_key():
    cache = _make_cache()
    cache.get = AsyncMock(side_effect=[5, None])  # version=5, no cached list
    entity = _stub_entity()
    session = _make_session([entity])
    repo = TodoQueryRepository(session, cache, "u1", MagicMock())

    await repo.list()

    # The set call should use a key containing v5
    set_call = cache.set.call_args
    assert "v5" in set_call[0][0]


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cache_hit():
    cached_data = {
        "id": "t1",
        "title": "buy milk",
        "completed": False,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
        "created_by": "u1",
        "updated_by": "u1",
    }
    cache = _make_cache()
    cache.get.return_value = cached_data
    session = _make_session()
    repo = TodoQueryRepository(session, cache, "u1", MagicMock())

    result = await repo.get("t1")

    assert isinstance(result, TodoRead)
    assert result.id == "t1"
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_cache_miss_found():
    entity = _stub_entity(id="t1")
    cache = _make_cache()
    session = _make_session([entity])
    repo = TodoQueryRepository(session, cache, "u1", MagicMock())

    result = await repo.get("t1")

    assert isinstance(result, TodoRead)
    session.scalars.assert_awaited_once()
    cache.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_cache_miss_not_found():
    cache = _make_cache()
    session = _make_session([])  # empty result
    repo = TodoQueryRepository(session, cache, "u1", MagicMock())

    result = await repo.get("t1")

    assert result is None
    cache.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_with_null_cache_queries_db():
    """NullCache falls back gracefully to DB."""
    entity = _stub_entity(id="t1")
    session = _make_session([entity])
    repo = TodoQueryRepository(session, NullCache(), "u1", MagicMock())

    result = await repo.get("t1")

    assert isinstance(result, TodoRead)
    session.scalars.assert_awaited_once()
