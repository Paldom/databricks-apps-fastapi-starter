import io
import os
from collections.abc import AsyncGenerator
from logging import Logger
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.agents.adapters.genie_adapter import GenieAdapter
from app.agents.contracts import ResponsesAgentRequest
from app.core.config import Settings
from app.core.databricks.ai_gateway import AiGatewayAdapter
from app.core.databricks.jobs import JobsAdapter
from app.core.databricks.knowledge_assistant import KnowledgeAssistantClient
from app.core.databricks.serving import ServingAdapter
from app.core.databricks.uc_files import UcFilesAdapter
from app.core.databricks.vector_search import VectorSearchAdapter
from app.core.deps import (
    get_ai_client,
    get_current_user,
    get_logger,
    get_settings,
    get_user_ai_client,
    get_user_info,
    get_user_workspace_client,
    get_workspace_client,
)
from app.core.errors import ConfigurationError, NotFoundError, RequestTooLargeError
from app.core.integrations import databricks_integrations_disabled_message
from app.models.user_dto import CurrentUser, UserInfo


def _examples_enabled(settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Showcase routes exist only when ENABLE_EXAMPLES=true (dev target by default)."""
    if not settings.enable_examples:
        raise NotFoundError("Examples are disabled; set ENABLE_EXAMPLES=true")


# Every example route requires an authenticated user and the feature flag.
router = APIRouter(
    prefix="/examples",
    tags=["examples"],
    dependencies=[Depends(get_current_user), Depends(_examples_enabled)],
)


class ExampleMessage(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)


class ExampleRow(BaseModel):
    id: str = Field(..., max_length=255)
    data: str = Field(..., max_length=65_536)


class ExampleTitle(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class GenieQuestion(BaseModel):
    content: str = Field(..., min_length=1, max_length=8192)


class AgentMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str = Field(..., min_length=1, max_length=8192)


class AgentQuestion(BaseModel):
    messages: list[AgentMessage] = Field(..., min_length=1, max_length=20)


def _require_databricks_integrations(settings: Settings) -> None:
    if not settings.databricks_integrations_enabled():
        raise ConfigurationError(databricks_integrations_disabled_message())


def _require_serving_endpoint(settings: Settings) -> str:
    _require_databricks_integrations(settings)
    endpoint = settings.serving_endpoint_name
    if not endpoint:
        raise ConfigurationError("SERVING_ENDPOINT_NAME not configured")
    return endpoint


def _require_job_id(settings: Settings) -> int:
    _require_databricks_integrations(settings)
    if not settings.job_id:
        raise ConfigurationError("JOB_ID not configured")
    return int(settings.job_id)


def _require_embedding_model(settings: Settings) -> str:
    _require_databricks_integrations(settings)
    model = settings.ai_gateway_embedding_model
    if not model:
        raise ConfigurationError("AI_GATEWAY_EMBEDDING_MODEL not configured")
    return model


def _require_knowledge_assistant_endpoint(settings: Settings) -> str:
    _require_databricks_integrations(settings)
    endpoint = settings.knowledge_assistant_endpoint
    if not endpoint:
        raise ConfigurationError("KNOWLEDGE_ASSISTANT_ENDPOINT not configured")
    return endpoint


@router.get("/secret")
async def bound_secret(settings: Annotated[Settings, Depends(get_settings)]):
    """Show that a bundle-bound secret reached the app; the value itself never leaves it."""
    if not (settings.example_secret and settings.example_secret.get_secret_value()):
        raise ConfigurationError(
            "EXAMPLE_SECRET not bound (secret binding in the app resource)"
        )
    return {"configured": True}


@router.post("/serving")
async def serving(
    request: Request,
    rows: list[ExampleRow],
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
):
    endpoint = _require_serving_endpoint(settings)
    adapter = ServingAdapter(get_user_workspace_client(request), logger)
    records = [row.model_dump() for row in rows]
    dataframe_split = {
        "columns": list(records[0].keys()) if records else [],
        "data": [list(record.values()) for record in records],
    }
    return await adapter.query(
        endpoint,
        dataframe_split,
        timeout=float(settings.serving_timeout_seconds),
    )


@router.post("/job", status_code=202)
async def run_job(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
    params: dict[str, Any] | None = Body(default=None),
):
    """Start the bound job; poll GET /job/{run_id} (the ingress cuts long requests)."""
    job_id = _require_job_id(settings)
    adapter = JobsAdapter(get_user_workspace_client(request), logger)
    run_id = await adapter.run_now(job_id=job_id, notebook_params=params)
    return {"run_id": run_id, "state": "PENDING"}


@router.get("/job/{run_id}")
async def get_job_run(
    run_id: int,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
):
    job_id = int(_require_job_id(settings))
    adapter = JobsAdapter(get_user_workspace_client(request), logger, job_id=job_id)
    return await adapter.run_state(run_id)


@router.post("/embed")
async def embed(
    request: Request,
    body: ExampleTitle,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
):
    model = _require_embedding_model(settings)
    adapter = AiGatewayAdapter(get_ai_client(request), logger)
    vector = await adapter.embed(model, body.title)
    return {"vector": vector}


@router.post("/vector/query")
async def vector_query(
    request: Request,
    body: ExampleTitle,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
    user: Annotated[UserInfo, Depends(get_user_info)],
):
    model = _require_embedding_model(settings)
    ai_adapter = AiGatewayAdapter(get_ai_client(request), logger)
    vector_adapter = VectorSearchAdapter(
        get_workspace_client(request), settings.vector_search_index_name or "", logger
    )

    vector = await ai_adapter.embed(model, body.title)
    return await vector_adapter.similarity_search(
        ["chunk_text", "doc_uri"],
        query_vector=vector,
        filters={"user_id": user.user_id},
        num_results=3,
        timeout=float(settings.vector_timeout_seconds),
    )


@router.post("/genie/{space_id}/ask")
async def genie_ask(
    request: Request,
    space_id: str,
    body: GenieQuestion,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Ask a Genie Agent one question through the unified Genie adapter."""
    _require_databricks_integrations(settings)
    adapter = GenieAdapter(get_user_workspace_client(request), space_id)
    result = await adapter.invoke(
        ResponsesAgentRequest.model_validate(
            {"input": [{"role": "user", "content": body.content}]}
        )
    )
    return result.response.model_dump()


@router.post("/uc/upload")
async def upload(
    request: Request,
    relative_path: str,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    max_bytes = settings.max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(8192)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise RequestTooLargeError(
                f"Upload exceeds maximum size of {max_bytes} bytes"
            )
        chunks.append(chunk)

    adapter = UcFilesAdapter(get_user_workspace_client(request), logger)
    data = b"".join(chunks)
    # Each user writes under their own subtree so uploads cannot overwrite others' files.
    user_path = f"{user.id}/{relative_path}"
    uploaded_bytes = await adapter.upload(settings.volume_root, user_path, data)
    return {"uploaded": user_path, "bytes": uploaded_bytes}


@router.get("/uc/download")
async def download(
    request: Request,
    relative_path: str,
    logger: Annotated[Logger, Depends(get_logger)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    adapter = UcFilesAdapter(get_user_workspace_client(request), logger)
    content = await adapter.download(settings.volume_root, f"{user.id}/{relative_path}")
    filename = quote(os.path.basename(relative_path))
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/agent/ask")
async def agent_ask(
    request: Request,
    body: AgentQuestion,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
):
    """Ask the Knowledge Assistant endpoint through the Responses API."""
    endpoint = _require_knowledge_assistant_endpoint(settings)
    adapter = KnowledgeAssistantClient(get_user_ai_client(request), logger)
    messages: list[Any] = [m.model_dump() for m in body.messages]
    response = await adapter.ask(endpoint, messages)
    return response.model_dump()


@router.post("/agent/ask/stream")
async def agent_ask_stream(
    request: Request,
    body: AgentQuestion,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
):
    """Stream Knowledge Assistant Responses events as server-sent events."""
    endpoint = _require_knowledge_assistant_endpoint(settings)
    adapter = KnowledgeAssistantClient(get_user_ai_client(request), logger)
    messages: list[Any] = [m.model_dump() for m in body.messages]

    async def events() -> AsyncGenerator[str, None]:
        async for event in adapter.ask_stream(endpoint, messages):
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
