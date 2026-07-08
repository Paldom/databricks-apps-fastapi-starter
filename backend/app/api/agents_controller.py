"""Thin Responses-compatible invocation surface for internal testing and evaluation.

Accepts ``ResponsesAgentRequest`` bodies, dispatches to the matching backend
adapter, and returns ``ResponsesAgentResponse``.  This is *not* the main
chat UI endpoint — it exists for eval scripts, curl-based debugging, and
future feedback linkage.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.agents.factory import get_agent_adapter, list_available_backends
from app.core.config import Settings
from app.core.deps import get_current_user, get_settings
from app.core.errors import http_error
from app.models.user_dto import CurrentUser

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
        raise http_error(404, f"Backend '{backend}' is not configured or unavailable")

    try:
        agent_request = ResponsesAgentRequest(**body)
    except Exception as exc:
        raise http_error(422, f"Invalid request body: {exc}") from exc

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


class FeedbackRequest(BaseModel):
    """User feedback on an agent answer, linked to its MLflow trace."""

    trace_id: str = Field(..., min_length=1, max_length=200)
    value: bool | float | str
    rationale: str | None = Field(default=None, max_length=4000)
    name: str = Field(default="user_feedback", max_length=100)


@router.post("/feedback", status_code=201)
async def submit_feedback(
    payload: FeedbackRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, str]:
    """Attach human feedback to a trace (closes the golden-path loop).

    The chat stream and ``/invocations`` responses surface trace ids
    (``downstream_trace_id`` / ``trace_id``); the UI posts them back here and
    MLflow stores the assessment on the trace for evaluation and monitoring.
    """
    import mlflow
    from mlflow.entities import AssessmentSource, AssessmentSourceType

    try:
        assessment = mlflow.log_feedback(
            trace_id=payload.trace_id,
            name=payload.name,
            value=payload.value,
            rationale=payload.rationale,
            source=AssessmentSource(
                source_type=AssessmentSourceType.HUMAN,
                source_id=current_user.id,
            ),
        )
    except Exception as exc:
        raise http_error(502, f"Failed to record feedback: {exc}") from exc

    return {"assessment_id": assessment.assessment_id or ""}
