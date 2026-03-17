import io
import os
import uuid
from collections.abc import AsyncGenerator
from logging import Logger
from typing import Annotated, Any

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
from app.core.security.rate_limit import limiter
from app.models.user_dto import UserInfo


router = APIRouter(tags=["Examples"])


class ExampleMessage(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)


class ExampleRow(BaseModel):
    id: str = Field(..., max_length=255)
    data: str = Field(..., max_length=65_536)


class ExampleTitle(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class GenieQuestion(BaseModel):
    content: str = Field(..., min_length=1, max_length=8192)


def _require_serving_endpoint(settings: Settings) -> str:
    endpoint = settings.serving_endpoint_name
    if not endpoint:
        raise ConfigurationError("SERVING_ENDPOINT_NAME not configured")
    return endpoint


def _require_job_id(settings: Settings) -> int:
    if not settings.job_id:
        raise ConfigurationError("JOB_ID not configured")
    return int(settings.job_id)


async def _get_genie_adapter(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> AsyncGenerator[GenieAdapter, None]:
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
@limiter.limit("20/minute")
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
@limiter.limit("5/minute")
async def run_job(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
    params: dict[str, Any] | None = Body(default=None),
):
    adapter = JobsAdapter(get_workspace_client(request), logger)
    return await adapter.run_and_get_output(
        job_id=_require_job_id(settings),
        notebook_params=params,
        timeout=float(settings.job_timeout_seconds),
    )


@router.post("/embed")
@limiter.limit("20/minute")
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
@limiter.limit("10/minute")
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
@limiter.limit("20/minute")
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
@limiter.limit("5/minute")
async def genie_start_conversation(
    request: Request,
    space_id: str,
    body: GenieQuestion,
    adapter: Annotated[GenieAdapter, Depends(_get_genie_adapter)],
):
    return await adapter.start_conversation(space_id, body.content)


@router.post("/genie/{space_id}/{conversation_id}/ask")
@limiter.limit("20/minute")
async def genie_follow_up(
    request: Request,
    space_id: str,
    conversation_id: str,
    body: GenieQuestion,
    adapter: Annotated[GenieAdapter, Depends(_get_genie_adapter)],
):
    return await adapter.follow_up(space_id, conversation_id, body.content)


@router.post("/uc/upload")
@limiter.limit("10/minute")
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
@limiter.limit("20/minute")
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
