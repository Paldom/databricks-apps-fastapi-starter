from __future__ import annotations

from app.repositories.chat_repository import ChatRepository


class ChatService:
    def __init__(self, repo: ChatRepository, user_id: str) -> None:
        self._repo = repo
        self._user_id = user_id

    async def list_project_chats(
        self,
        project_id: str,
        cursor: str | None,
        limit: int,
    ) -> dict:
        chats, next_cursor, has_more = await self._repo.list_project_chats(
            self._user_id,
            project_id,
            cursor,
            limit,
        )
        items = [
            {
                "id": str(c.id),
                "title": c.title or "",
                "project_id": c.project_id or "",
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c in chats
        ]
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    async def create_chat(self, project_id: str, title: str) -> dict:
        chat = await self._repo.create_chat(self._user_id, project_id, title)
        return {
            "id": str(chat.id),
            "title": chat.title or "",
            "project_id": chat.project_id or "",
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
        }

    async def update_chat(self, chat_id: str, title: str | None) -> dict | None:
        chat = await self._repo.update_chat(self._user_id, chat_id, title)
        if chat is None:
            return None
        return {
            "id": str(chat.id),
            "title": chat.title or "",
            "project_id": chat.project_id or "",
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
        }

    async def set_title_if_empty(self, chat_id: str, title: str) -> dict | None:
        """Set title only if the chat currently has no title."""
        chat = await self._repo.set_title_if_empty(self._user_id, chat_id, title)
        if chat is None:
            return None
        return {
            "id": str(chat.id),
            "title": chat.title or "",
            "project_id": chat.project_id or "",
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
        }

    async def delete_chat(self, chat_id: str) -> bool:
        return await self._repo.delete_chat(self._user_id, chat_id)

    async def get_owned_chat(self, chat_id: str) -> dict | None:
        chat = await self._repo.get_owned_chat(self._user_id, chat_id)
        if chat is None:
            return None
        return {
            "id": str(chat.id),
            "title": chat.title or "",
            "project_id": chat.project_id or "",
            "genie_conversation_id": chat.genie_conversation_id,
        }

    async def list_messages(self, chat_id: str, cursor: str | None, limit: int) -> dict:
        rows, next_cursor, has_more = await self._repo.list_messages(
            self._user_id, chat_id, cursor, limit
        )
        items = [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "parts": m.parts or [],
                "trace_id": m.trace_id,
                "created_at": m.created_at,
            }
            for m in rows
        ]
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    async def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        parts: list[dict] | None = None,
        trace_id: str | None = None,
    ) -> str:
        message = await self._repo.add_message(
            self._user_id, chat_id, role, content, parts or [], trace_id
        )
        return str(message.id)

    async def set_genie_conversation(self, chat_id: str, conversation_id: str) -> None:
        await self._repo.set_genie_conversation(self._user_id, chat_id, conversation_id)

    async def search_chats(self, q: str, cursor: str | None, limit: int) -> dict:
        items, next_cursor, has_more = await self._repo.search_chats(
            self._user_id,
            q,
            cursor,
            limit,
        )
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    async def get_recent_chats(self, limit: int) -> dict:
        items = await self._repo.get_recent_chats(self._user_id, limit)
        return {
            "items": items,
            "next_cursor": None,
            "has_more": False,
        }
