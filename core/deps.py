from asyncpg import Pool
from databricks.sdk import WorkspaceClient

from config import Settings, settings
from core.database import pg_pool
from core.vector_search import get_vector_index as _get_vector_index
from workspace import w
from fastapi import Request
from openai import AsyncOpenAI

from core.auth import UserInfo
from core.errors import http_error
from modules.users.schemas import CurrentUser
from logging import Logger
from core.logging import get_logger as _get_logger


def get_pg_pool() -> Pool:
    if not pg_pool:
        raise RuntimeError("PostgreSQL pool not initialised")
    return pg_pool


def get_settings() -> Settings:
    return settings


def get_workspace_client(request: Request = None) -> WorkspaceClient:  # type: ignore[assignment]
    """Return a WorkspaceClient either from the request state or create one."""
    if request is not None:
        return getattr(request.state, "w", w())
    return w()


def get_current_user(request: Request) -> CurrentUser:
    """Require an authenticated user or raise 401."""
    user: CurrentUser | None = getattr(request.state, "user", None)
    if user is None:
        raise http_error(401, "Authentication required")
    return user


def get_current_user_optional(request: Request) -> CurrentUser | None:
    """Return authenticated user or None (no 401)."""
    return getattr(request.state, "user", None)


def get_user_info(request: Request) -> UserInfo:
    """Backward-compatible bridge: derive UserInfo from CurrentUser."""
    user: CurrentUser | None = getattr(request.state, "user", None)
    if user is not None:
        return UserInfo(
            preferred_username=user.preferred_username,
            user_id=user.id,
            email=user.email,
        )
    return UserInfo()


def get_ai_client(request: Request) -> AsyncOpenAI:
    return request.app.state.ai_client

def get_vector_index():
    return _get_vector_index()

def get_logger() -> Logger:
    return _get_logger()
