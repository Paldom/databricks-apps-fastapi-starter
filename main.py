import os, json, asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import asyncpg, pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from databricks.sdk.service.serving import DataframeSplitInput

from workspace import w
from config import get_secret

load_dotenv()

DBX_ENDPOINT = get_secret("SERVING_ENDPOINT_NAME")
JOB_ID       = get_secret("JOB_ID")

PG_DSN = {
    "host":     get_secret("PG_HOST"),
    "port": int(get_secret("PG_PORT") or 5432),
    "database": get_secret("PG_DB"),
    "user":     get_secret("PG_USER"),
    "password": get_secret("PG_PASSWORD"),
}

class Message(BaseModel):
    text: str

class GenericRow(BaseModel):
    id: str
    data: str

pg_pool: Optional[asyncpg.Pool] = None

@asynccontextmanager
async def lifespan(app):
    global pg_pool
    pg_pool = await asyncpg.create_pool(**PG_DSN, min_size=1, max_size=4)
    yield
    await pg_pool.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health():
    return {"ok": True}

@app.post("/pg")
async def pg_demo(msg: Message):
    if not pg_pool:
        raise HTTPException(500, "PostgreSQL pool not initialised")
    row = await pg_pool.fetchrow(
        "INSERT INTO demo(text) VALUES ($1) RETURNING id, text", msg.text
    )
    return dict(row)

@app.post("/serving")
async def serving(rows: List[GenericRow]):
    if not DBX_ENDPOINT:
        raise HTTPException(500, "SERVING_ENDPOINT_NAME not configured")
    df = pd.DataFrame([r.model_dump() for r in rows])
    df_split = DataframeSplitInput.from_dict(df.to_dict(orient="split"))
    try:
        resp = await asyncio.to_thread(
            w().serving_endpoints.query,
            name=DBX_ENDPOINT,
            dataframe_split=df_split,
        )
        return resp.as_dict()
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/job")
async def run_job(params: Dict[str, Any] | None = None):
    if not JOB_ID:
        raise HTTPException(500, "JOB_ID not configured")
    try:
        finished = await asyncio.to_thread(
            w().jobs.run_now_and_wait,
            job_id=int(JOB_ID),
            notebook_params=params or {},
        )
        last_task_id = finished.tasks[-1].run_id
        out = await asyncio.to_thread(
            w().jobs.get_run_output,
            run_id=last_task_id,
        )
        return json.loads(out.notebook_output.result)
    except Exception as e:
        raise HTTPException(500, str(e))
