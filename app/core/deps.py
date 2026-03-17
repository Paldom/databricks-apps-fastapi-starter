from __future__ import annotations

from logging import Logger
from typing import TYPE_CHECKING, Annotated, Any

from databricks.sdk import WorkspaceClient
from fastapi import Depends, Request
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.cache import Cache, NullCache
from app.core.config import Settings, settings
from app.core.db.deps import get_async_session, get_engine  # noqa: F401 – re-export
from app.core.errors import (
    AuthenticationError,
    ConfigurationError,
    ServiceUnavailableError,
)
from app.core.logging import get_logger as _get_logger
from app.core.runtime import AppRuntime, get_app_runtime
from app.models.user_dto import CurrentUser, UserInfo

if TYPE_CHECKING:
    from app.repositories.chat_repository import ChatRepository
    from app.repositories.document_repository import DocumentRepository
    from app.repositories.project_repository import ProjectRepository
    from app.repositories.user_settings_repository import UserSettingsRepository
    from app.services.chat_service import ChatService
    from app.services.chat_stream_service import ChatStreamService
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


def get_runtime(request: Request) -> AppRuntime:
    return get_app_runtime(request.app)


def get_workspace_client(request: Request) -> WorkspaceClient:
    request_client = getattr(request.state, "w", None)
    if request_client is not None:
        return request_client

    runtime = get_runtime(request)
    if runtime.workspace_client is not None:
        return runtime.workspace_client

    detail = runtime.error_for("workspace_client")
    if detail:
        raise ServiceUnavailableError(
            f"Databricks workspace client is unavailable: {detail}"
        )
    raise ConfigurationError("Databricks workspace client is not configured")


def get_ai_client(request: Request) -> AsyncOpenAI:
    runtime = get_runtime(request)
    client = runtime.ai_client
    if client is not None:
        return client

    detail = runtime.error_for("ai_client") or runtime.error_for("workspace_client")
    if detail:
        raise ServiceUnavailableError(f"AI client is unavailable: {detail}")
    raise ConfigurationError(
        "AI integration is not configured; set SERVING_ENDPOINT_NAME"
    )


def get_vector_index(request: Request) -> Any:
    runtime = get_runtime(request)
    idx = runtime.vector_index
    if idx is None:
        detail = runtime.error_for("vector_index")
        if detail:
            raise ServiceUnavailableError(
                f"Vector Search index is unavailable: {detail}"
            )
        raise ConfigurationError(
            "Vector Search is not configured; set VECTOR_SEARCH_ENDPOINT_NAME and "
            "VECTOR_SEARCH_INDEX_NAME"
        )
    return idx


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


def get_cache(request: Request) -> Cache:
    """Provide the application-level cache instance."""
    runtime = get_runtime(request)
    cache = getattr(runtime, "cache", None)
    if cache is not None:
        return cache
    return NullCache()


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


def get_chat_stream_service(
    request: Request,
) -> ChatStreamService:
    from app.services.chat_stream_service import ChatStreamService
    ai_client = get_ai_client(request)
    return ChatStreamService(ai_client)
