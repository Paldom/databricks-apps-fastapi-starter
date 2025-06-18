import json
import asyncio
import uuid
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from core.errors import http_error
from pydantic import BaseModel
from modules.todo.schemas import TodoCreate
from databricks.sdk.service.serving import DataframeSplitInput

from databricks.sdk import WorkspaceClient
from openai import AsyncOpenAI, OpenAIError

from config import Settings
from core.deps import (
    get_pg_pool,
    get_settings,
    get_workspace_client,
    get_ai_client,
    get_vector_index,
    get_user_info,
    get_logger,
)
from core.auth import UserInfo
from databricks.vector_search.index import VectorSearchIndex
from logging import Logger


router = APIRouter()


class Message(BaseModel):
    text: str


class GenericRow(BaseModel):
    id: str
    data: str


async def _embed_text(client: AsyncOpenAI, model: str, text: str) -> list[float]:
    """Return embedding vector for the given text."""
    rsp = await client.embeddings.create(
        model=model,
        input=text,
        extra_body={"usage_context": {"source": "fastapi-demo"}},
    )
    return rsp.data[0].embedding


@router.post("/pg")
async def pg_demo(
    msg: Message,
    pool = Depends(get_pg_pool),
    logger: Logger = Depends(get_logger),
):
    logger.debug("Inserting demo row")
    row = await pool.fetchrow(
        "INSERT INTO demo(text) VALUES ($1) RETURNING id, text",
        msg.text,
    )
    return dict(row)


@router.post("/serving")
async def serving(
    rows: List[GenericRow],
    settings: Settings = Depends(get_settings),
    ws: WorkspaceClient = Depends(get_workspace_client),
    logger: Logger = Depends(get_logger),
):
    endpoint = settings.serving_endpoint_name
    if not endpoint:
        raise http_error(500, "SERVING_ENDPOINT_NAME not configured")
    df = pd.DataFrame([r.model_dump() for r in rows])
    df_split = DataframeSplitInput.from_dict(df.to_dict(orient="split"))
    try:
        logger.info("Querying serving endpoint %s", endpoint)
        resp = await asyncio.to_thread(
            ws.serving_endpoints.query,
            name=endpoint,
            dataframe_split=df_split,
        )
        return resp.as_dict()
    except Exception as e:
        raise http_error(500, str(e))


@router.post("/job")
async def run_job(
    params: Dict[str, Any] | None = None,
    settings: Settings = Depends(get_settings),
    ws: WorkspaceClient = Depends(get_workspace_client),
    logger: Logger = Depends(get_logger),
):
    job_id = settings.job_id
    if not job_id:
        raise http_error(500, "JOB_ID not configured")
    try:
        logger.info("Triggering job %s", job_id)
        finished = await asyncio.to_thread(
            ws.jobs.run_now_and_wait,
            job_id=int(job_id),
            notebook_params=params or {},
        )
        last_task_id = finished.tasks[-1].run_id  # type: ignore[index]
        out = await asyncio.to_thread(
            ws.jobs.get_run_output,
            run_id=last_task_id,  # type: ignore[arg-type]
        )
        return json.loads(out.notebook_output.result)  # type: ignore[union-attr,arg-type]
    except Exception as e:
        raise http_error(500, str(e))


@router.post("/embed")
async def embed(
    todo: TodoCreate,
    settings: Settings = Depends(get_settings),
    client: AsyncOpenAI = Depends(get_ai_client),
    logger: Logger = Depends(get_logger),
):
    endpoint = settings.serving_endpoint_name
    if not endpoint:
        raise http_error(500, "SERVING_ENDPOINT_NAME not configured")
    try:
        logger.info("Embedding todo title using endpoint %s", endpoint)
        vector = await _embed_text(client, endpoint, todo.title)
        return {"vector": vector}
    except OpenAIError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector/store")
async def vector_store(
    todo: TodoCreate,
    settings: Settings = Depends(get_settings),
    client: AsyncOpenAI = Depends(get_ai_client),
    index: VectorSearchIndex = Depends(get_vector_index),
    user: UserInfo = Depends(get_user_info),
):
    endpoint = settings.serving_endpoint_name
    if not endpoint:
        raise http_error(500, "SERVING_ENDPOINT_NAME not configured")
    vector = await _embed_text(client, endpoint, todo.title)
    doc = {
        "id": str(uuid.uuid4()),
        "values": vector,
        "metadata": {"user": user.user_id},
        "text": todo.title,
    }
    await asyncio.to_thread(index.upsert, [doc])
    return {"id": doc["id"], "vector": vector}


@router.post("/vector/query")
async def vector_query(
    todo: TodoCreate,
    settings: Settings = Depends(get_settings),
    client: AsyncOpenAI = Depends(get_ai_client),
    index: VectorSearchIndex = Depends(get_vector_index),
    user: UserInfo = Depends(get_user_info),
):
    endpoint = settings.serving_endpoint_name
    if not endpoint:
        raise http_error(500, "SERVING_ENDPOINT_NAME not configured")
    vector = await _embed_text(client, endpoint, todo.title)
    results = await asyncio.to_thread(
        index.similarity_search,
        columns=["text"],
        query_vector=vector,
        filters={"user": user.user_id},
        num_results=3,
    )
    return results


