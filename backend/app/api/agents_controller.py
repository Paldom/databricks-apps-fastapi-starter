"""Thin Responses-compatible invocation surface for internal testing and evaluation.

Accepts ``ResponsesAgentRequest`` bodies, dispatches to the matching backend
adapter, and returns ``ResponsesAgentResponse``.  This is *not* the main
chat UI endpoint — it exists for eval scripts, curl-based debugging, and
future feedback linkage.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agents.factory import get_agent_adapter, list_available_backends
from app.core.config import Settings
from app.core.deps import get_settings

router = APIRouter(prefix="/agents", tags=["agents"])
_logger = logging.getLogger(__name__)


def _try_get_ai_client(request: Request) -> Any:
    try:
        from app.core.deps import get_ai_client

        return get_ai_client(request)
    except Exception:
        _logger.debug("AI client unavailable for agents route", exc_info=True)
        return None


def _try_get_workspace_client(request: Request) -> Any:
    try:
        from app.core.deps import get_workspace_client

        return get_workspace_client(request)
    except Exception:
        _logger.debug("Workspace client unavailable for agents route", exc_info=True)
        return None


@router.get("/backends")
async def list_backends(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, list[str]]:
    """Return the list of configured agent backends."""
    ai_client = _try_get_ai_client(request)
    workspace_client = _try_get_workspace_client(request)
    backends = list_available_backends(
        settings,
        ai_client=ai_client,
        workspace_client=workspace_client,
    )
    return {"backends": backends}


@router.post("/{backend}/invocations")
async def invoke_agent(
    backend: str,
    body: dict[str, Any],
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Invoke an agent backend with a Responses-compatible request body.

    The request body should contain at minimum an ``input`` field with a list
    of message objects.  Returns the full ``ResponsesAgentResponse`` as a dict.
    """
    from mlflow.types.responses import ResponsesAgentRequest

    ai_client = _try_get_ai_client(request)
    workspace_client = _try_get_workspace_client(request)

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

    try:
        agent_request = ResponsesAgentRequest(**body)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid request body: {exc}",
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
