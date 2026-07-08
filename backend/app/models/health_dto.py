from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class HealthStatus(StrEnum):
    OK = "ok"
    FAIL = "fail"


class DependencyCheck(BaseModel):
    status: HealthStatus
    reason: str | None = None


class LiveResponse(BaseModel):
    ok: bool = True


class ReadyResponse(BaseModel):
    ok: bool
    db: bool


class DetailedHealthResponse(BaseModel):
    ok: bool
    database: DependencyCheck
    workspace: DependencyCheck
    ai: DependencyCheck
    vector_search: DependencyCheck
