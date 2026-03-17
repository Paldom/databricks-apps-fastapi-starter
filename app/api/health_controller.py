import time
from logging import Logger
from typing import Annotated

from fastapi import APIRouter, Depends
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.databricks.vector_search import VectorSearchAdapter
from app.core.deps import (
    get_ai_client,
    get_engine,
    get_logger,
    get_settings,
    get_vector_search_adapter,
)
from app.core.observability import (
    get_tracer,
    increment_counter,
    record_duration,
    tag_exception,
)

router = APIRouter(prefix="/health", tags=["Health"])

_tracer = get_tracer()


@router.get("/live")
async def live() -> dict[str, bool]:
    return {"ok": True}


async def _check_dependency(
    name: str, coro, *, span_name: str | None = None
) -> bool:
    """Run a single dependency probe inside a child span."""
    t0 = time.monotonic()
    with _tracer.start_as_current_span(span_name or f"health.check.{name}") as span:
        try:
            await coro()
            result = "ok"
            span.set_attribute("result", "ok")
            return True
        except Exception as exc:
            result = "error"
            tag_exception(span, exc)
            return False
        finally:
            elapsed = time.monotonic() - t0
            attrs = {"dependency": name, "result": result}
            record_duration("app.dependency.call.duration", elapsed, attrs)
            increment_counter("app.dependency.call.count", attributes=attrs)


async def _probe_db(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _probe_ai(client: AsyncOpenAI, endpoint: str) -> None:
    await client.embeddings.create(model=endpoint, input="ping")


async def _probe_vector(adapter: VectorSearchAdapter) -> None:
    await adapter.describe()


@router.get("/ready")
async def ready(
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    client: Annotated[AsyncOpenAI, Depends(get_ai_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    vs_adapter: Annotated[VectorSearchAdapter, Depends(get_vector_search_adapter)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> dict[str, bool]:
    t0 = time.monotonic()
    with _tracer.start_as_current_span("health.ready"):
        logger.debug("Running readiness checks")

        db_ok = await _check_dependency("db", lambda: _probe_db(engine))
        cache_ok = True
        broker_ok = True

        if settings.serving_endpoint_name:
            ai_ok = await _check_dependency(
                "ai", lambda: _probe_ai(client, settings.serving_endpoint_name)
            )
        else:
            ai_ok = True

        vector_ok = await _check_dependency(
            "vector", lambda: _probe_vector(vs_adapter)
        )

        all_ok = db_ok and cache_ok and broker_ok and ai_ok and vector_ok

        result = "ok" if all_ok else "error"
        elapsed = time.monotonic() - t0
        record_duration("app.health.readiness.duration", elapsed)
        increment_counter(
            "app.health.readiness.count", attributes={"result": result}
        )

    return {
        "ok": all_ok,
        "db": db_ok,
        "cache": cache_ok,
        "broker": broker_ok,
        "ai": ai_ok,
        "vector_search": vector_ok,
    }
