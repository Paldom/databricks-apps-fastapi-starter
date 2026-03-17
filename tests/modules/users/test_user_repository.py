import pytest
from unittest.mock import AsyncMock, MagicMock

from app.repositories.user_repository import get_or_create_user
from app.models.user_model import AppUser


@pytest.mark.asyncio
async def test_creates_new_user():
    session = AsyncMock()
    session.get.return_value = None

    async def fake_refresh(obj):
        obj.id = "u1"
        obj.email = "a@b.com"
        obj.preferred_username = "alice"
        obj.name = "alice"

    session.refresh = fake_refresh

    result = await get_or_create_user(
        session, user_id="u1", email="a@b.com", preferred_username="alice"
    )
    session.add.assert_called_once()
    session.commit.assert_awaited()
    assert result.id == "u1"


@pytest.mark.asyncio
async def test_updates_existing_user():
    existing = AppUser(
        id="u1",
        email="old@b.com",
        preferred_username="old_name",
        name="old_name",
    )
    session = AsyncMock()
    session.get.return_value = existing

    result = await get_or_create_user(
        session, user_id="u1", email="new@b.com", preferred_username="new_name"
    )
    assert result.email == "new@b.com"
    assert result.preferred_username == "new_name"
    assert result.name == "new_name"
    session.commit.assert_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_name_falls_back_to_email():
    session = AsyncMock()
    session.get.return_value = None

    async def fake_refresh(obj):
        pass

    session.refresh = fake_refresh

    result = await get_or_create_user(
        session, user_id="u1", email="a@b.com", preferred_username=None
    )
    assert result.name == "a@b.com"


@pytest.mark.asyncio
async def test_name_falls_back_to_user_id():
    session = AsyncMock()
    session.get.return_value = None

    async def fake_refresh(obj):
        pass

    session.refresh = fake_refresh

    result = await get_or_create_user(
        session, user_id="u1", email=None, preferred_username=None
    )
    assert result.name == "u1"
