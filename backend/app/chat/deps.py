"""FastAPI wiring for the chat supervisor.

The compiled LangGraph graph, its tools and the supervisor LLM are built once per
process on first use and cached on the app runtime. Per-request identity (the
on-behalf-of workspace client) reaches tools through ``app.core.context`` rather than
through the graph, so building once is safe.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import Request

from app.chat.memory import create_checkpointer
from app.chat.orchestrator import ChatOrchestrator
from app.core.config import Settings
from app.core.deps import (
    _get_request_settings,
    get_ai_client,
    get_logger,
    get_runtime,
)
from app.core.integrations import ensure_workspace_client

_build_lock = asyncio.Lock()


def _build_supervisor_llm(ai_client: Any, settings: Settings) -> Any:
    """LangChain chat model that reuses the token-refreshing Databricks client."""
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr

    sync_client = getattr(ai_client, "sync_client", None)
    # api_key is required by the model's validator but never sent: every request goes
    # through the injected Databricks clients, which authenticate per call.
    return ChatOpenAI(
        model=settings.supervisor_model,
        api_key=SecretStr("unused"),
        base_url=str(ai_client.base_url),
        async_client=ai_client.chat.completions,
        client=sync_client.chat.completions if sync_client is not None else None,
        root_async_client=ai_client,
        root_client=sync_client,
    )


async def _build_orchestrator(request: Request) -> ChatOrchestrator:
    from app.chat.agent import build_agent
    from app.chat.registry import build_supervisor_prompt, get_enabled_specs
    from app.chat.tools import build_tools

    runtime = get_runtime(request)
    settings = _get_request_settings(request)
    ai_client = get_ai_client(request)
    log = get_logger()

    enabled_specs = get_enabled_specs(settings)
    tools = build_tools(
        enabled_specs,
        settings,
        ai_client=ai_client,
        workspace_client=ensure_workspace_client(runtime, settings),
        logger=log,
    )
    prompt = build_supervisor_prompt(enabled_specs)
    checkpointer = create_checkpointer(settings)
    agent = build_agent(
        _build_supervisor_llm(ai_client, settings), tools, prompt, checkpointer
    )
    return ChatOrchestrator(agent, checkpointer, log)


async def get_chat_orchestrator(request: Request) -> ChatOrchestrator:
    runtime = get_runtime(request)
    if runtime.chat_orchestrator is None:
        async with _build_lock:
            if runtime.chat_orchestrator is None:
                runtime.chat_orchestrator = await _build_orchestrator(request)
    return runtime.chat_orchestrator
