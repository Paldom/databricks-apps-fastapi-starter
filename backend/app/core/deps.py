from __future__ import annotations

from logging import Logger
from typing import TYPE_CHECKING, Annotated, Any

from databricks.sdk import WorkspaceClient
from fastapi import Depends, Request
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings, settings
from app.core.db.deps import get_async_session, get_engine  # noqa: F401 – re-export
from app.core.errors import AuthenticationError
from app.core.integrations import ensure_ai_client, ensure_vector_index, ensure_workspace_client
from app.core.logging import get_logger as _get_logger
from app.core.runtime import AppRuntime, get_app_runtime
from app.models.user_dto import CurrentUser, UserInfo

if TYPE_CHECKING:
    from app.chat.orchestrator import ChatOrchestrator
    from app.repositories.chat_repository import ChatRepository
    from app.repositories.document_repository import DocumentRepository
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.user_settings_repository import UserSettingsRepository
    from app.services.chat_service import ChatService
    from app.services.document_service import DocumentService
    from app.services.project_service import ProjectService
    from app.services.user_settings_service import UserSettingsService

# ---------------------------------------------------------------------------
# Shared / leaf dependencies
# ---------------------------------------------------------------------------


def get_settings() -> Settings:
    return settings


def get_logger() -> Logger:
    return _get_logger()


def _get_request_settings(request: Request) -> Settings:
    override = request.app.dependency_overrides.get(get_settings)
    if override is not None:
        return override()
    return settings


def get_runtime(request: Request) -> AppRuntime:
    return get_app_runtime(request.app)


def get_workspace_client(request: Request) -> WorkspaceClient:
    request_client = getattr(request.state, "w", None)
    if request_client is not None:
        return request_client

    runtime = get_runtime(request)
    return ensure_workspace_client(runtime, _get_request_settings(request))


def get_ai_client(request: Request) -> AsyncOpenAI:
    runtime = get_runtime(request)
    return ensure_ai_client(runtime, _get_request_settings(request))


def get_vector_index(request: Request) -> Any:
    runtime = get_runtime(request)
    return ensure_vector_index(runtime, _get_request_settings(request))


def get_current_user(request: Request) -> CurrentUser:
    user: CurrentUser | None = getattr(request.state, "user", None)
    if user is None:
        raise AuthenticationError()
    return user


def get_current_user_optional(request: Request) -> CurrentUser | None:
    return getattr(request.state, "user", None)


def get_user_info(request: Request) -> UserInfo:
    user: CurrentUser | None = getattr(request.state, "user", None)
    if user is not None:
        return UserInfo(
            preferred_username=user.preferred_username,
            user_id=user.id,
            email=user.email,
        )
    return UserInfo()


# ---------------------------------------------------------------------------
# Frontend contract dependencies
# ---------------------------------------------------------------------------


def get_project_repo(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ProjectRepository:
    from app.repositories.project_repository import ProjectRepository
    return ProjectRepository(session)


def get_chat_repo(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ChatRepository:
    from app.repositories.chat_repository import ChatRepository
    return ChatRepository(session)


def get_document_repo(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DocumentRepository:
    from app.repositories.document_repository import DocumentRepository
    return DocumentRepository(session)


def get_user_settings_repo(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> UserSettingsRepository:
    from app.repositories.user_settings_repository import UserSettingsRepository
    return UserSettingsRepository(session)


def get_project_service(
    repo: Annotated[Any, Depends(get_project_repo)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ProjectService:
    from app.services.project_service import ProjectService
    return ProjectService(repo, user.id)


def get_chat_service(
    repo: Annotated[Any, Depends(get_chat_repo)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ChatService:
    from app.services.chat_service import ChatService
    return ChatService(repo, user.id)


def get_document_service(
    repo: Annotated[Any, Depends(get_document_repo)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DocumentService:
    from app.services.document_service import DocumentService
    return DocumentService(repo, user.id)


def get_user_settings_service(
    repo: Annotated[Any, Depends(get_user_settings_repo)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> UserSettingsService:
    from app.services.user_settings_service import UserSettingsService
    return UserSettingsService(
        repo, user.id,
        default_name=user.name or user.id,
        default_email=user.email,
    )


def _try_get_workspace_client(request: Request) -> Any:
    """Return the workspace client or ``None`` if not available."""
    try:
        return get_workspace_client(request)
    except Exception:
        return None


def _try_get_vector_index(request: Request) -> Any:
    """Return the vector index or ``None`` if not available."""
    try:
        return get_vector_index(request)
    except Exception:
        return None


def get_chat_orchestrator(
    request: Request,
) -> ChatOrchestrator:
    from langchain_openai import ChatOpenAI

    from app.chat.agent import build_agent
    from app.chat.memory import create_checkpointer
    from app.chat.orchestrator import ChatOrchestrator
    from app.chat.registry import build_supervisor_prompt, get_enabled_specs
    from app.chat.tools import build_tools

    runtime = get_runtime(request)
    s = _get_request_settings(request)
    ai_client = get_ai_client(request)
    log = _get_logger()

    # Checkpointer (from runtime if initialized at startup)
    checkpointer = getattr(runtime, "langgraph_checkpointer", None)
    if checkpointer is None:
        checkpointer = create_checkpointer(s)

    # Registry → enabled specs → tools + prompt
    enabled_specs = get_enabled_specs(s)
    tools = build_tools(
        enabled_specs, s,
        ai_client=ai_client,
        workspace_client=_try_get_workspace_client(request),
        vector_index=_try_get_vector_index(request),
        logger=log,
    )
    prompt = build_supervisor_prompt(enabled_specs)

    # Build agent
    model_name = (
        s.supervisor_model
        or s.serving_endpoint_name
        or "databricks-meta-llama-3-1-70b-instruct"
    )
    supervisor_llm = ChatOpenAI(
        model=model_name,
        api_key=ai_client.api_key,
        base_url=str(ai_client.base_url),
        timeout=float(s.openai_timeout_seconds),
    )
    agent = build_agent(supervisor_llm, tools, prompt, checkpointer)

    return ChatOrchestrator(agent, checkpointer, log)
