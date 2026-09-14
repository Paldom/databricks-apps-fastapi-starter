"""Chats and documents can only be attached to projects the caller owns."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import NotFoundError
from app.repositories.chat_repository import ChatRepository
from app.repositories.document_repository import DocumentRepository


def _session_returning(scalar):
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_create_chat_rejects_foreign_project():
    repo = ChatRepository(_session_returning(None))
    with pytest.raises(NotFoundError):
        await repo.create_chat("user-b", "proj-of-user-a", "title")


@pytest.mark.asyncio
async def test_create_chat_accepts_owned_project():
    session = _session_returning("proj-1")
    repo = ChatRepository(session)
    chat = await repo.create_chat("user-a", "proj-1", "title")
    assert chat.project_id == "proj-1"
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_document_rejects_foreign_project():
    repo = DocumentRepository(_session_returning(None))
    with pytest.raises(NotFoundError):
        await repo.create_document(
            owner_user_id="user-b",
            filename="f.pdf",
            content_type="application/pdf",
            size_bytes=1,
            storage_path="/x",
            project_id="proj-of-user-a",
        )
