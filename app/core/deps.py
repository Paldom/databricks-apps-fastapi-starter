from collections.abc import AsyncGenerator
from logging import Logger
from typing import Annotated, Any

from databricks.sdk import WorkspaceClient
from fastapi import Depends, Request
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings, settings
from app.core.databricks.ai_gateway import AiGatewayAdapter
from app.core.databricks.genie import GenieAdapter
from app.core.databricks.jobs import JobsAdapter
from app.core.databricks.serving import ServingAdapter
from app.core.databricks.sql_delta import SqlDeltaAdapter
from app.core.databricks.uc_files import UcFilesAdapter
from app.core.databricks.vector_search import VectorSearchAdapter
from app.core.databricks.workspace import get_workspace_client_singleton
from app.core.db.deps import get_async_session, get_engine  # noqa: F401 – re-export
from app.core.errors import AuthenticationError
from app.core.logging import get_logger as _get_logger
from app.models.user_dto import CurrentUser, UserInfo
from app.repositories.delta_todo_repository import DeltaTodoRepository
from app.repositories.lakebase_demo_repository import LakebaseDemoRepository
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


def get_workspace_client(request: Request = None) -> WorkspaceClient:  # type: ignore[assignment]
    if request is not None:
        return getattr(request.state, "w", get_workspace_client_singleton())
    return get_workspace_client_singleton()


def get_ai_client(request: Request) -> AsyncOpenAI:
    return request.app.state.ai_client


def get_vector_index(request: Request) -> Any:
    idx = getattr(request.app.state, "vector_index", None)
    if idx is None:
        raise RuntimeError("Vector Search index not initialised")
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
) -> VectorSearchAdapter:
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
        timeout=30.0,
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
    repo: Annotated[TodoRepository, Depends(get_todo_repo)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> TodoService:
    return TodoService(repo, user, logger)


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
