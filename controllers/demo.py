import json
import asyncio
import uuid

import io
import os
from typing import Any, Dict, List, cast

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from httpx import AsyncClient
from core.errors import http_error
from pydantic import BaseModel
from modules.todo.schemas import TodoCreate, TodoRead
from databricks.sdk.service.serving import DataframeSplitInput

from databricks.sdk import WorkspaceClient
from databricks import sql

# pyarrow is an optional dependency required only for Delta Table examples. Wrap the
# import in a try/except so the whole application (and its unit-tests) can still
# start even if the library is not installed in the environment.
#
# When ``pyarrow`` is not available we set ``pa`` to ``None`` and guard every
# code path that relies on it. A clear error will be returned if an endpoint is
# called that needs ``pyarrow``.

try:
    import pyarrow as pa  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    pa = None  # noqa: N816 – keep lowercase alias to mimic normal import

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

TABLE = "main.default.todo_demo"
SERVING_ENDPOINT_ERROR = "SERVING_ENDPOINT_NAME not configured"

def _get_sql_conn(settings: Settings):
    host = os.getenv("DATABRICKS_HOST")
    hostname = f"https://{host}" if host else None
    return sql.connect(
        server_hostname=hostname,
        http_path=settings.databricks_http_path,
        access_token=settings.databricks_token,
    )

def _genie_client(w: WorkspaceClient = Depends(get_workspace_client)) -> AsyncClient:
    """Return an AsyncClient for interacting with Genie."""
    return AsyncClient(
        base_url=f"https://{w.config.host}",
        headers={"Authorization": f"Bearer {w.config.token}"},
    )


async def _embed_text(client: AsyncOpenAI, model: str, text: str) -> list[float]:
    """Return embedding vector for the given text."""
    rsp = await client.embeddings.create(
        model=model,
        input=text,
        extra_body={"usage_context": {"source": "fastapi-demo"}},
    )
    return rsp.data[0].embedding

# Lakebase

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

# Serving Endpoint
  
@router.post("/serving")
async def serving(
    rows: List[GenericRow],
    settings: Settings = Depends(get_settings),
    w: WorkspaceClient = Depends(get_workspace_client),
    logger: Logger = Depends(get_logger),
):
    endpoint = settings.serving_endpoint_name
    if not endpoint:
        raise http_error(500, SERVING_ENDPOINT_ERROR)
    df = pd.DataFrame([r.model_dump() for r in rows])
    df_split = DataframeSplitInput.from_dict(df.to_dict(orient="split"))
    try:
        logger.info("Querying serving endpoint %s", endpoint)
        resp = await asyncio.to_thread(
            w.serving_endpoints.query,
            name=endpoint,
            dataframe_split=df_split,
        )
        return resp.as_dict()
    except Exception as e:
        raise http_error(500, str(e))

# Job

@router.post("/job")
async def run_job(
    params: Dict[str, Any] | None = None,
    settings: Settings = Depends(get_settings),
    w: WorkspaceClient = Depends(get_workspace_client),
    logger: Logger = Depends(get_logger),
):
    job_id = settings.job_id
    if not job_id:
        raise http_error(500, "JOB_ID not configured")
    try:
        logger.info("Triggering job %s", job_id)
        finished = await asyncio.to_thread(
            w.jobs.run_now_and_wait,
            job_id=int(job_id),
            notebook_params=params or {},
        )
        last_task_id = finished.tasks[-1].run_id
        out = await asyncio.to_thread(
            w.jobs.get_run_output,
            run_id=last_task_id,
        )
        return json.loads(out.notebook_output.result)
    except Exception as e:
        raise http_error(500, str(e))

# AI Gateway

@router.post("/embed")
async def embed(
    todo: TodoCreate,
    settings: Settings = Depends(get_settings),
    client: AsyncOpenAI = Depends(get_ai_client),
    logger: Logger = Depends(get_logger),
):
    endpoint = settings.serving_endpoint_name
    if not endpoint:
        raise http_error(500, SERVING_ENDPOINT_ERROR)
    try:
        logger.info("Embedding todo title using endpoint %s", endpoint)
        vector = await _embed_text(client, endpoint, todo.title)
        return {"vector": vector}
    except OpenAIError as e:
        raise HTTPException(status_code=500, detail=str(e))

# Vector Search Index

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
        raise http_error(500, SERVING_ENDPOINT_ERROR)
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
        raise http_error(500, SERVING_ENDPOINT_ERROR)
    vector = await _embed_text(client, endpoint, todo.title)
    results = await asyncio.to_thread(
        index.similarity_search,
        columns=["text"],
        query_vector=vector,
        filters={"user": user.user_id},
        num_results=3,
    )
    return results

# Delta Tables

@router.get("/delta/todos", response_model=List[TodoRead])
def list_delta_todos(
    limit: int = 100,
    settings: Settings = Depends(get_settings),
):
    if pa is None:
        # Avoid hard dependency when the endpoint is not used. This keeps the
        # service importable for test environments that don't install pyarrow.
        raise http_error(500, "pyarrow is required for Delta table operations but is not installed")
    query = f"SELECT id, title, completed FROM {TABLE} LIMIT %(lim)s"
    with _get_sql_conn(settings) as conn, conn.cursor() as cur:
        cur.execute(query, {"lim": limit})
        tbl: "pa.Table" = cur.fetchall_arrow()  # type: ignore[name-defined]
    return tbl.to_pandas().to_dict(orient="records")


@router.post("/delta/todos", status_code=201)
def add_delta_todo(
    todo: TodoCreate,
    settings: Settings = Depends(get_settings),
):
    stmt = (
        f"INSERT INTO {TABLE} (id, title, completed) VALUES (gen_random_uuid(), %(title)s, false)"
    )
    with _get_sql_conn(settings) as conn, conn.cursor() as cur:
        cur.execute(stmt, todo.model_dump())
    return {"title": todo.title}

# Genie

@router.post("/genie/{space_id}/ask")
async def genie_start_conversation(
    space_id: str,
    question: str,
    client: AsyncClient = Depends(_genie_client),
):
    body = {"content": question}
    resp = await client.post(
        f"/api/2.0/genie/spaces/{space_id}/start-conversation", json=body
    )
    resp.raise_for_status()
    return resp.json()


@router.post("/genie/{space_id}/{conversation_id}/ask")
async def genie_follow_up(
    space_id: str,
    conversation_id: str,
    question: str,
    client: AsyncClient = Depends(_genie_client),
):
    body = {"content": question}
    resp = await client.post(
        f"/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages",
        json=body,
    )
    resp.raise_for_status()
    return resp.json()


def _vol_uri(root: str, relative_path: str) -> str:
    relative = relative_path.lstrip("/")
    return f"{root}/{relative}"


@router.post("/uc/upload")
async def upload(
    relative_path: str,
    file: UploadFile = File(...),
    ws: WorkspaceClient = Depends(get_workspace_client),
    settings: Settings = Depends(get_settings),
):
    data = await file.read()
    ws.files.upload(
        _vol_uri(settings.volume_root, relative_path),
        io.BytesIO(data),
        overwrite=True,
    )
    return {"uploaded": relative_path, "bytes": len(data)}


@router.get("/uc/download")
def download(
    relative_path: str,
    ws: WorkspaceClient = Depends(get_workspace_client),
    settings: Settings = Depends(get_settings),
):
    resp = ws.files.download(_vol_uri(settings.volume_root, relative_path))
    if resp.contents is None:
        raise HTTPException(status_code=404, detail="Not found")
    stream = io.BytesIO(cast(bytes, resp.contents))
    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{os.path.basename(relative_path)}"'
            )
        },
    )


