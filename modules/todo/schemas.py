import uuid
import datetime as dt
from pydantic import BaseModel, Field


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    completed: bool | None = None


class TodoRead(BaseModel):
    id: uuid.UUID
    title: str
    completed: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    created_by: str
    updated_by: str
