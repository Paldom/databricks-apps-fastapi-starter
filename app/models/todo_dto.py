from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    completed: Optional[bool] = None


class TodoRead(BaseModel):
    id: str
    title: str
    completed: bool
    created_at: datetime | str
    updated_at: datetime | str
    created_by: str
    updated_by: str

    model_config = {"from_attributes": True}


def to_dto(entity) -> TodoRead:
    """Convert a Todo ORM entity to a TodoRead DTO."""
    return TodoRead.model_validate(entity)
