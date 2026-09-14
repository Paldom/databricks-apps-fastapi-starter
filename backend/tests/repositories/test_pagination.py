"""Keyset pagination on a real database: equal timestamps and interleaved ids never skip or repeat."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.db.base import Base
from app.core.errors import BadRequestError
from app.core.pagination import decode_cursor, encode_cursor
from app.models.chat_session_model import ChatSession
from app.models.file_record_model import FileRecord
from app.models.message_model import Message
from app.models.project_model import Project
from app.models.user_model import AppUser
from app.repositories.chat_repository import ChatRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.project_repository import ProjectRepository

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
OWNER = "user-a"


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        session.add(AppUser(id=OWNER, email="a@example.invalid"))
        session.add(AppUser(id="user-b", email="b@example.invalid"))
        for owner in (OWNER, "user-b"):
            session.add(
                Project(
                    id=f"proj-{owner}",
                    owner_user_id=owner,
                    name="p",
                )
            )
    yield factory
    await engine.dispose()


def _walk(pages: list[list[str]]) -> list[str]:
    seen: list[str] = []
    for page in pages:
        seen.extend(page)
    return seen


@pytest.mark.asyncio
async def test_chats_with_equal_timestamps_and_interleaved_ids(session_factory):
    ids = [uuid.UUID(int=n) for n in (7, 3, 9, 1, 5)]  # not monotonic
    async with session_factory() as session, session.begin():
        for n, chat_id in enumerate(ids):
            session.add(
                ChatSession(
                    id=chat_id,
                    user_id=OWNER,
                    project_id=f"proj-{OWNER}",
                    title=f"chat {n}",
                    created_at=T0,
                    updated_at=T0 if n < 3 else T0 + timedelta(seconds=1),
                    created_by=OWNER,
                    updated_by=OWNER,
                )
            )
        session.add(  # another owner's chat must never appear
            ChatSession(
                id=uuid.UUID(int=99),
                user_id="user-b",
                project_id="proj-user-b",
                title="other",
                created_at=T0,
                updated_at=T0,
                created_by="user-b",
                updated_by="user-b",
            )
        )
    async with session_factory() as session:
        repo = ChatRepository(session)
        pages, cursor = [], None
        while True:
            items, cursor, has_more = await repo.list_project_chats(
                OWNER, f"proj-{OWNER}", cursor, limit=2
            )
            pages.append([str(c.id) for c in items])
            if not has_more:
                break
    seen = _walk(pages)
    assert len(pages) == 3 and len(seen) == 5 and len(set(seen)) == 5
    assert set(seen) == {str(i) for i in ids}
    assert seen[:2] == [str(uuid.UUID(int=5)), str(uuid.UUID(int=1))]  # newest, id desc


@pytest.mark.asyncio
async def test_messages_ascending_and_documents_descending(session_factory):
    chat_id = uuid.UUID(int=42)
    async with session_factory() as session, session.begin():
        session.add(
            ChatSession(
                id=chat_id,
                user_id=OWNER,
                project_id=f"proj-{OWNER}",
                title="t",
                created_by=OWNER,
                updated_by=OWNER,
            )
        )
        for n in (4, 2, 8, 6):
            session.add(
                Message(
                    id=uuid.UUID(int=n),
                    session_id=chat_id,
                    user_id=OWNER,
                    role="user",
                    content=str(n),
                    parts=[{"type": "text", "text": str(n)}],
                    created_at=T0,
                    updated_at=T0,
                    created_by=OWNER,
                    updated_by=OWNER,
                )
            )
            session.add(
                FileRecord(
                    id=uuid.UUID(int=100 + n),
                    user_id=OWNER,
                    storage_path=f"/Volumes/x/{n}.pdf",
                    original_filename=f"{n}.pdf",
                    created_at=T0,
                    updated_at=T0,
                    created_by=OWNER,
                    updated_by=OWNER,
                )
            )
    async with session_factory() as session:
        chats = ChatRepository(session)
        docs = DocumentRepository(session)
        m_pages, cursor = [], None
        while True:
            items, cursor, more = await chats.list_messages(
                OWNER, str(chat_id), cursor, 3
            )
            m_pages.append([m.content for m in items])
            if not more:
                break
        d_pages, cursor = [], None
        while True:
            items, cursor, more = await docs.list_documents(OWNER, cursor, 3)
            d_pages.append([d.original_filename for d in items])
            if not more:
                break
    assert _walk(m_pages) == ["2", "4", "6", "8"]  # oldest first, id tie-break
    assert _walk(d_pages) == ["8.pdf", "6.pdf", "4.pdf", "2.pdf"]


@pytest.mark.asyncio
async def test_projects_page_without_gaps(session_factory):
    async with session_factory() as session, session.begin():
        for name in ("b", "a", "c"):
            session.add(
                Project(
                    id=f"proj-{name}",
                    owner_user_id=OWNER,
                    name=name,
                    created_at=T0,
                )
            )
    async with session_factory() as session:
        repo = ProjectRepository(session)
        pages, cursor = [], None
        while True:
            items, cursor, more = await repo.list_projects(OWNER, cursor, 2)
            pages.append([p["id"] for p in items])
            if not more:
                break
    seen = _walk(pages)
    assert len(seen) == 4 and len(set(seen)) == 4  # the fixture project plus three


def test_cursor_round_trip_and_garbage():
    cursor = encode_cursor(T0, uuid.UUID(int=1))
    assert decode_cursor(cursor) == (T0, str(uuid.UUID(int=1)))
    with pytest.raises(BadRequestError):
        decode_cursor("not-a-cursor")
