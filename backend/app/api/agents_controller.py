"""Thin Responses-compatible invocation surface for internal testing and evaluation.

Accepts ``ResponsesAgentRequest`` bodies, dispatches to the matching backend
adapter, and returns ``ResponsesAgentResponse``.  This is *not* the main
chat UI endpoint — it exists for eval scripts, curl-based debugging, and
future feedback linkage.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agents.factory import (
    KNOWN_BACKENDS,
    get_agent_adapter,
    list_available_backends,
)
from app.core.config import Settings
from app.core.context import log_fields
from app.core.deps import (
    CurrentUser,
    get_ai_client,
    get_current_user,
    get_settings,
    get_user_workspace_client,
    get_workspace_client,
)

router = APIRouter(
    prefix="/agents", tags=["agents"], dependencies=[Depends(get_current_user)]
)
_logger = logging.getLogger(__name__)


def _item_text(content: Any) -> str:
    """Plain text of a Responses input item: a string or a list of text parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part["text"]
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    return ""


async def _invoke_supervisor(
    request: Request, agent_request: Any, user: CurrentUser
) -> dict[str, Any]:
    """One non-streaming turn of this app's own LangGraph supervisor."""
    from app.agents.response_utils import text_to_response
    from app.chat.context import ChatContext
    from app.chat.deps import get_chat_orchestrator

    messages = [
        {"role": item.get("role", "user"), "content": text}
        for item in agent_request.model_dump()["input"]
        if isinstance(item, dict) and (text := _item_text(item.get("content")))
    ]
    if not messages:
        raise HTTPException(status_code=422, detail="input has no text messages")
    custom_inputs = agent_request.custom_inputs or {}
    public_thread_id = str(custom_inputs.get("thread_id") or uuid4())
    orchestrator = await get_chat_orchestrator(request)
    log_fields.set({"session_id": public_thread_id, "user_id": user.id})
    # Stateless by design (evals, curl): the transcript is the request, nothing is stored.
    text, trace_id = await orchestrator.invoke(
        messages,
        ChatContext(user_id=user.id, user_email=user.email, chat_id=public_thread_id),
    )
    response = text_to_response(text, custom_outputs={"thread_id": public_thread_id})
    payload = response.model_dump()
    payload["_meta"] = {"source": "supervisor", "downstream_trace_id": trace_id}
    return payload


@router.get("/backends")
async def list_backends(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, list[str]]:
    """Return the list of configured agent backends."""
    return {"backends": list_available_backends(settings)}


@router.post("/{backend}/invocations")
async def invoke_agent(
    backend: str,
    body: dict[str, Any],
    request: Request,
    settings: Settings = Depends(get_settings),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Invoke an agent backend with a Responses-compatible request body.

    The request body should contain at minimum an ``input`` field with a list
    of message objects.  Returns the full ``ResponsesAgentResponse`` as a dict.
    """
    from mlflow.types.responses import ResponsesAgentRequest

    if backend != "supervisor" and backend not in KNOWN_BACKENDS:
        raise HTTPException(
            status_code=404,
            detail=f"Backend '{backend}' is not configured or unavailable",
        )
    try:
        agent_request = ResponsesAgentRequest(**body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid request body: {exc}")

    if backend == "supervisor":
        return await _invoke_supervisor(request, agent_request, user)

    # Same identity rules as the chat tools: Genie runs as the user under OBO
    # (401 without a forwarded token); model calls use the app identity.
    ai_client = get_ai_client(request) if backend != "genie" else None
    workspace_client = None
    if backend == "genie":
        workspace_client = (
            get_user_workspace_client(request)
            if settings.enable_obo
            else get_workspace_client(request)
        )

    adapter = get_agent_adapter(
        backend,
        settings=settings,
        ai_client=ai_client,
        workspace_client=workspace_client,
    )
    if adapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"Backend '{backend}' is not configured or unavailable",
        )

    result = await adapter.invoke(agent_request)

    response_dict = (
        result.response.model_dump()
        if hasattr(result.response, "model_dump")
        else dict(result.response)
    )
    response_dict["_meta"] = {
        "source": result.source,
        "downstream_trace_id": result.downstream_trace_id,
    }
    return response_dict
