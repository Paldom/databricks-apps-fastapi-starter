from __future__ import annotations

from logging import Logger
from typing import TYPE_CHECKING, Annotated, Any

from databricks.sdk import WorkspaceClient
from fastapi import Depends, Request
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.db.deps import get_async_session, get_engine  # noqa: F401 – re-export
from app.core.errors import AuthenticationError
from app.core.integrations import (
    ensure_ai_client,
    ensure_workspace_client,
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
    """The app's own (service principal) workspace client."""
    runtime = get_runtime(request)
    return ensure_workspace_client(runtime, _get_request_settings(request))


def get_user_workspace_client(request: Request) -> WorkspaceClient:
    """Workspace client acting as the calling user (OBO).

    Fails closed: with ENABLE_OBO on, a request without a forwarded user token
    gets 401 rather than silently falling back to the service principal.
    With OBO off, user-scoped operations run as the app identity.
    """
    settings = _get_request_settings(request)
    user_client = getattr(request.state, "w", None)
    if user_client is not None:
        return user_client
    if settings.enable_obo:
        raise AuthenticationError("User authorization is required for this operation")
    return get_workspace_client(request)


def get_ai_client(request: Request) -> AsyncOpenAI:
    """Model client bound to the app identity (token-refreshing)."""
    runtime = get_runtime(request)
    return ensure_ai_client(runtime, _get_request_settings(request))


def get_user_ai_client(request: Request) -> AsyncOpenAI:
    """Model client acting as the calling user when OBO is on, else the app client."""
    user_client = getattr(request.state, "w", None)
    if user_client is None:
        if _get_request_settings(request).enable_obo:
            raise AuthenticationError(
                "User authorization is required for this operation"
            )
        return get_ai_client(request)
    from databricks_openai import AsyncDatabricksOpenAI

    return AsyncDatabricksOpenAI(
        workspace_client=user_client,
        timeout=float(_get_request_settings(request).openai_timeout_seconds),
    )


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
        repo,
        user.id,
        default_name=user.name or user.id,
        default_email=user.email,
    )
