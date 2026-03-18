from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/stream", tags=["stream"])


async def _event_generator(count: int):
    for i in range(count):
        yield f"event: message\ndata: chunk-{i}\n\n"
        await asyncio.sleep(0.01)
    yield "event: done\ndata: complete\n\n"


@router.get("/sse", operation_id="streamSSE")
async def stream_sse(
    count: int = Query(default=3, ge=1, le=20),
) -> StreamingResponse:
    """Server-Sent Events demo endpoint."""
    return StreamingResponse(
        _event_generator(count),
        media_type="text/event-stream",
    )
