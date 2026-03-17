from collections.abc import AsyncGenerator
from logging import Logger
from typing import Annotated, Any

from databricks.sdk import WorkspaceClient
from fastapi import Depends, Request
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.cache import Cache, NullCache
from app.core.config import Settings, settings
from app.core.databricks.ai_gateway import AiGatewayAdapter
from app.core.databricks.genie import GenieAdapter
from app.core.databricks.jobs import JobsAdapter
from app.core.databricks.serving import ServingAdapter
from app.core.databricks.sql_delta import SqlDeltaAdapter
from app.core.databricks.uc_files import UcFilesAdapter
from app.core.databricks.vector_search import VectorSearchAdapter
from app.core.db.deps import get_async_session, get_engine  # noqa: F401 – re-export
from app.core.errors import (
    AuthenticationError,
    ConfigurationError,
    ServiceUnavailableError,
)
from app.core.logging import get_logger as _get_logger
from app.core.runtime import AppRuntime, get_app_runtime
from app.models.user_dto import CurrentUser, UserInfo
from app.repositories.delta_todo_repository import DeltaTodoRepository
from app.repositories.lakebase_demo_repository import LakebaseDemoRepository
from app.repositories.todo_command_repository import TodoCommandRepository
from app.repositories.todo_query_repository import TodoQueryRepository
from app.repositories.todo_repository import TodoRepository
from app.services.integrations.ai_gateway_service import AiGatewayService
from app.services.integrations.genie_service import GenieService
from app.services.integrations.jobs_service import JobsService
from app.services.integrations.lakebase_demo_service import LakebaseDemoService
from app.services.integrations.serving_service import ServingService
from app.services.integrations.sql_delta_service import SqlDeltaService
from app.services.integrations.uc_files_service import UcFilesService
from app.services.integrations.vector_search_service import VectorSearchService
from app.services.todo_service import TodoService


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
# Adapter factories
# ---------------------------------------------------------------------------


def get_serving_adapter(
    request: Request,
    logger: Annotated[Logger, Depends(get_logger)],
) -> ServingAdapter:
    return ServingAdapter(get_workspace_client(request), logger)


def get_jobs_adapter(
    request: Request,
    logger: Annotated[Logger, Depends(get_logger)],
) -> JobsAdapter:
    return JobsAdapter(get_workspace_client(request), logger)


def get_ai_gateway_adapter(
    request: Request,
    logger: Annotated[Logger, Depends(get_logger)],
) -> AiGatewayAdapter:
    return AiGatewayAdapter(get_ai_client(request), logger)


def get_vector_search_adapter(
    request: Request,
    logger: Annotated[Logger, Depends(get_logger)],
    s: Annotated[Settings, Depends(get_settings)],
) -> VectorSearchAdapter:
    if not s.has_vector_search_config():
        raise ConfigurationError(
            "Vector Search is not configured; set VECTOR_SEARCH_ENDPOINT_NAME and "
            "VECTOR_SEARCH_INDEX_NAME"
        )
    return VectorSearchAdapter(get_vector_index(request), logger)


def get_sql_delta_adapter(
    logger: Annotated[Logger, Depends(get_logger)],
) -> SqlDeltaAdapter:
    return SqlDeltaAdapter(settings, logger)


async def get_genie_adapter(
    request: Request,
    logger: Annotated[Logger, Depends(get_logger)],
) -> AsyncGenerator[GenieAdapter, None]:
    from httpx import AsyncClient

    ws = get_workspace_client(request)
    async with AsyncClient(
        base_url=f"https://{ws.config.host}",
        headers={"Authorization": f"Bearer {ws.config.token}"},
        timeout=float(settings.genie_timeout_seconds),
    ) as client:
        yield GenieAdapter(client, logger)


def get_uc_files_adapter(
    request: Request,
    logger: Annotated[Logger, Depends(get_logger)],
) -> UcFilesAdapter:
    return UcFilesAdapter(get_workspace_client(request), logger)


# ---------------------------------------------------------------------------
# Repository factories
# ---------------------------------------------------------------------------


def get_todo_repo(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TodoRepository:
    return TodoRepository(session)


def get_todo_query_repo(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    cache: Annotated[Cache, Depends(get_cache)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    logger: Annotated[Logger, Depends(get_logger)],
    s: Annotated[Settings, Depends(get_settings)],
) -> TodoQueryRepository:
    return TodoQueryRepository(
        session,
        cache,
        user.id,
        logger,
        detail_ttl=s.cache_todo_detail_ttl,
        list_ttl=s.cache_todo_list_ttl,
    )


def get_todo_command_repo(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    cache: Annotated[Cache, Depends(get_cache)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    logger: Annotated[Logger, Depends(get_logger)],
    s: Annotated[Settings, Depends(get_settings)],
) -> TodoCommandRepository:
    return TodoCommandRepository(
        session,
        cache,
        user.id,
        logger,
        detail_ttl=s.cache_todo_detail_ttl,
    )


def get_lakebase_repo(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> LakebaseDemoRepository:
    return LakebaseDemoRepository(session)


def get_delta_todo_repo(
    adapter: Annotated[SqlDeltaAdapter, Depends(get_sql_delta_adapter)],
) -> DeltaTodoRepository:
    return DeltaTodoRepository(adapter)


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_todo_service(
    query_repo: Annotated[TodoQueryRepository, Depends(get_todo_query_repo)],
    command_repo: Annotated[TodoCommandRepository, Depends(get_todo_command_repo)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> TodoService:
    return TodoService(query_repo, command_repo, user, logger)


def get_lakebase_service(
    repo: Annotated[LakebaseDemoRepository, Depends(get_lakebase_repo)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> LakebaseDemoService:
    return LakebaseDemoService(repo, logger)


def get_serving_service(
    adapter: Annotated[ServingAdapter, Depends(get_serving_adapter)],
    s: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> ServingService:
    return ServingService(adapter, s, logger)


def get_jobs_service(
    adapter: Annotated[JobsAdapter, Depends(get_jobs_adapter)],
    s: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> JobsService:
    return JobsService(adapter, s, logger)


def get_ai_gateway_service(
    adapter: Annotated[AiGatewayAdapter, Depends(get_ai_gateway_adapter)],
    s: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> AiGatewayService:
    return AiGatewayService(adapter, s, logger)


def get_vector_search_service(
    ai_adapter: Annotated[AiGatewayAdapter, Depends(get_ai_gateway_adapter)],
    vs_adapter: Annotated[VectorSearchAdapter, Depends(get_vector_search_adapter)],
    s: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> VectorSearchService:
    return VectorSearchService(ai_adapter, vs_adapter, s, logger)


def get_sql_delta_service(
    repo: Annotated[DeltaTodoRepository, Depends(get_delta_todo_repo)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> SqlDeltaService:
    return SqlDeltaService(repo, logger)


def get_genie_service(
    adapter: Annotated[GenieAdapter, Depends(get_genie_adapter)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> GenieService:
    return GenieService(adapter, logger)


def get_uc_files_service(
    adapter: Annotated[UcFilesAdapter, Depends(get_uc_files_adapter)],
    s: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> UcFilesService:
    return UcFilesService(adapter, s, logger)
