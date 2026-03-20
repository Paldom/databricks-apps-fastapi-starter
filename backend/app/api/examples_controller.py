import io
import os
import uuid
from collections.abc import AsyncGenerator
from logging import Logger
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, Body, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from httpx import AsyncClient
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.databricks.ai_gateway import AiGatewayAdapter
from app.core.databricks.genie import GenieAdapter
from app.core.databricks.jobs import JobsAdapter
from app.core.databricks.knowledge_assistant import KnowledgeAssistantAdapter
from app.core.databricks.serving import ServingAdapter
from app.core.databricks.uc_files import UcFilesAdapter
from app.core.databricks.vector_search import VectorSearchAdapter
from app.core.db.deps import get_async_session
from app.core.deps import (
    get_ai_client,
    get_logger,
    get_settings,
    get_user_info,
    get_vector_index,
    get_workspace_client,
)
from app.core.errors import ConfigurationError, RequestTooLargeError
from app.core.integrations import databricks_integrations_disabled_message
from app.models.user_dto import UserInfo


router = APIRouter(prefix="/examples", tags=["examples"])


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


def _require_knowledge_assistant_endpoint(settings: Settings) -> str:
    _require_databricks_integrations(settings)
    endpoint = settings.knowledge_assistant_endpoint
    if not endpoint:
        raise ConfigurationError("KNOWLEDGE_ASSISTANT_ENDPOINT not configured")
    return endpoint


async def _get_genie_adapter(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> AsyncGenerator[GenieAdapter, None]:
    _require_databricks_integrations(settings)
    ws = get_workspace_client(request)
    async with AsyncClient(
        base_url=f"https://{ws.config.host}",
        headers={"Authorization": f"Bearer {ws.config.token}"},
        timeout=float(settings.genie_timeout_seconds),
    ) as client:
        yield GenieAdapter(client, logger)


@router.post("/pg")
async def pg_demo(
    msg: ExampleMessage,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    logger: Annotated[Logger, Depends(get_logger)],
):
    logger.debug("Inserting demo row")
    result = await session.execute(
        text("INSERT INTO demo(text) VALUES (:text) RETURNING id, text"),
        {"text": msg.text},
    )
    return dict(result.mappings().one())


@router.post("/serving")
async def serving(
    request: Request,
    rows: list[ExampleRow],
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
):
    endpoint = _require_serving_endpoint(settings)
    adapter = ServingAdapter(get_workspace_client(request), logger)
    df = pd.DataFrame([row.model_dump() for row in rows])
    return await adapter.query(
        endpoint,
        df.to_dict(orient="split"),
        timeout=float(settings.serving_timeout_seconds),
    )


@router.post("/job")
async def run_job(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
    params: dict[str, Any] | None = Body(default=None),
):
    job_id = _require_job_id(settings)
    adapter = JobsAdapter(get_workspace_client(request), logger)
    return await adapter.run_and_get_output(
        job_id=job_id,
        notebook_params=params,
        timeout=float(settings.job_timeout_seconds),
    )


@router.post("/embed")
async def embed(
    request: Request,
    body: ExampleTitle,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
):
    endpoint = _require_serving_endpoint(settings)
    adapter = AiGatewayAdapter(get_ai_client(request), logger)
    vector = await adapter.embed(endpoint, body.title)
    return {"vector": vector}


@router.post("/vector/store")
async def vector_store(
    request: Request,
    body: ExampleTitle,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
    user: Annotated[UserInfo, Depends(get_user_info)],
):
    endpoint = _require_serving_endpoint(settings)
    ai_adapter = AiGatewayAdapter(get_ai_client(request), logger)
    vector_adapter = VectorSearchAdapter(get_vector_index(request), logger)

    vector = await ai_adapter.embed(endpoint, body.title)
    doc = {
        "id": str(uuid.uuid4()),
        "values": vector,
        "metadata": {"user": user.user_id},
        "text": body.title,
    }
    await vector_adapter.upsert(
        [doc],
        timeout=float(settings.vector_timeout_seconds),
    )
    return {"id": doc["id"], "vector": vector}


@router.post("/vector/query")
async def vector_query(
    request: Request,
    body: ExampleTitle,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
    user: Annotated[UserInfo, Depends(get_user_info)],
):
    endpoint = _require_serving_endpoint(settings)
    ai_adapter = AiGatewayAdapter(get_ai_client(request), logger)
    vector_adapter = VectorSearchAdapter(get_vector_index(request), logger)

    vector = await ai_adapter.embed(endpoint, body.title)
    return await vector_adapter.similarity_search(
        query_vector=vector,
        columns=["text"],
        filters={"user": user.user_id},
        num_results=3,
        timeout=float(settings.vector_timeout_seconds),
    )


@router.post("/genie/{space_id}/ask")
async def genie_start_conversation(
    request: Request,
    space_id: str,
    body: GenieQuestion,
    adapter: Annotated[GenieAdapter, Depends(_get_genie_adapter)],
):
    return await adapter.start_conversation(space_id, body.content)


@router.post("/genie/{space_id}/{conversation_id}/ask")
async def genie_follow_up(
    request: Request,
    space_id: str,
    conversation_id: str,
    body: GenieQuestion,
    adapter: Annotated[GenieAdapter, Depends(_get_genie_adapter)],
):
    return await adapter.follow_up(space_id, conversation_id, body.content)


@router.post("/uc/upload")
async def upload(
    request: Request,
    relative_path: str,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
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

    adapter = UcFilesAdapter(get_workspace_client(request), logger)
    data = b"".join(chunks)
    uploaded_bytes = await adapter.upload(settings.volume_root, relative_path, data)
    return {"uploaded": relative_path, "bytes": uploaded_bytes}


@router.get("/uc/download")
async def download(
    request: Request,
    relative_path: str,
    logger: Annotated[Logger, Depends(get_logger)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    adapter = UcFilesAdapter(get_workspace_client(request), logger)
    content = await adapter.download(settings.volume_root, relative_path)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{os.path.basename(relative_path)}"'
            )
        },
    )


async def _get_ka_adapter(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> AsyncGenerator[KnowledgeAssistantAdapter, None]:
    _require_knowledge_assistant_endpoint(settings)
    ws = get_workspace_client(request)
    async with AsyncClient(
        base_url=f"https://{ws.config.host}",
        headers={"Authorization": f"Bearer {ws.config.token}"},
        timeout=float(settings.knowledge_assistant_timeout_seconds),
    ) as client:
        yield KnowledgeAssistantAdapter(client, logger)


@router.post("/agent/ask")
async def agent_ask(
    request: Request,
    body: AgentQuestion,
    settings: Annotated[Settings, Depends(get_settings)],
    adapter: Annotated[KnowledgeAssistantAdapter, Depends(_get_ka_adapter)],
):
    endpoint = _require_knowledge_assistant_endpoint(settings)
    return await adapter.ask(endpoint, [m.model_dump() for m in body.messages])


@router.post("/agent/ask/stream")
async def agent_ask_stream(
    request: Request,
    body: AgentQuestion,
    settings: Annotated[Settings, Depends(get_settings)],
    adapter: Annotated[KnowledgeAssistantAdapter, Depends(_get_ka_adapter)],
):
    endpoint = _require_knowledge_assistant_endpoint(settings)
    return StreamingResponse(
        adapter.ask_stream(endpoint, [m.model_dump() for m in body.messages]),
        media_type="text/event-stream",
    )
