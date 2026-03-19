from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ConfigDict

from app.api.common.schemas import ApiModel, CursorPage
from app.core.deps import get_project_service
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


class Project(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "work",
                "name": "Work",
                "createdAt": "2024-01-15T10:00:00Z",
                "chatCount": 2,
            }
        }
    )

    id: str
    name: str
    created_at: datetime
    chat_count: int


class PaginatedProjects(CursorPage[Project]):
    pass


class CreateProjectRequest(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "New Project"}}
    )

    name: str


class UpdateProjectRequest(ApiModel):
    name: str | None = None


def _to_project(d: dict) -> Project:
    return Project(
        id=d["id"],
        name=d["name"],
        created_at=d["created_at"],
        chat_count=d["chat_count"],
    )


@router.get(
    "",
    operation_id="listProjects",
    response_model=PaginatedProjects,
)
async def list_projects(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    service: ProjectService = Depends(get_project_service),
) -> PaginatedProjects:
    result = await service.list_projects(cursor=cursor, limit=limit)
    return PaginatedProjects(
        items=[_to_project(i) for i in result["items"]],
        next_cursor=result["next_cursor"],
        has_more=result["has_more"],
    )


@router.post(
    "",
    operation_id="createProject",
    response_model=Project,
    status_code=201,
)
async def create_project(
    body: CreateProjectRequest,
    service: ProjectService = Depends(get_project_service),
) -> Project:
    result = await service.create_project(name=body.name)
    return _to_project(result)


@router.patch(
    "/{projectId}",
    operation_id="updateProject",
    response_model=Project,
)
async def update_project(
    projectId: str,
    body: UpdateProjectRequest,
    service: ProjectService = Depends(get_project_service),
) -> Project:
    result = await service.update_project(project_id=projectId, name=body.name or "")
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_project(result)


@router.delete(
    "/{projectId}",
    operation_id="deleteProject",
    status_code=204,
)
async def delete_project(
    projectId: str,
    service: ProjectService = Depends(get_project_service),
) -> Response:
    deleted = await service.delete_project(project_id=projectId)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return Response(status_code=204)
