from asyncpg import Pool
from databricks.sdk import WorkspaceClient

from config import Settings, settings
from core.database import pg_pool
from core.vector_search import get_vector_index as _get_vector_index
from workspace import w
from fastapi import Request
from openai import AsyncOpenAI

from core.auth import UserInfo
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


def get_user_info(request: Request) -> UserInfo:
    return request.state.user_info


def get_ai_client(request: Request) -> AsyncOpenAI:
    return request.app.state.ai_client

def get_vector_index():
    return _get_vector_index()

def get_logger() -> Logger:
    return _get_logger()

