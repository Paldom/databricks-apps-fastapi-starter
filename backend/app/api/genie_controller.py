"""Poll a Genie turn that outlived the tool deadline (Genie's ids are the handle)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.agents.adapters.genie_adapter import GenieAdapter
from app.core.config import Settings
from app.core.deps import (
    get_chat_service,
    get_current_user,
    get_settings,
    get_user_workspace_client,
)
from app.core.errors import ConfigurationError
from app.services.chat_service import ChatService

router = APIRouter(
    prefix="/chats", tags=["genie"], dependencies=[Depends(get_current_user)]
)


@router.get("/{chatId}/genie/{messageId}", operation_id="getGenieMessage")
async def get_genie_message(
    chatId: str,
    messageId: str,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    chats: ChatService = Depends(get_chat_service),
) -> dict[str, Any]:
    """202 while Genie is still working, 200 with text/SQL/rows once it finished."""
    if not settings.genie_space_id:
        raise ConfigurationError("GENIE_SPACE_ID not configured")
    chat = await chats.get_owned_chat(chatId)
    if chat is None or not chat["genie_conversation_id"]:
        raise HTTPException(
            status_code=404, detail="Chat or Genie conversation not found"
        )
    adapter = GenieAdapter(get_user_workspace_client(request), settings.genie_space_id)
    result = await adapter.status(chat["genie_conversation_id"], messageId)
    if result["status"] == "pending":
        response.status_code = 202
    return {
        "status": result["status"],
        "text": result["text"],
        "sql": result["sql"],
        "rows": result.get("rows", []),
        "conversation_id": result["conversation_id"],
        "message_id": result["message_id"],
    }
