from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class DependencyHealthStatus(str, Enum):
    OK = "ok"
    FAIL = "fail"
    NOT_CONFIGURED = "not_configured"
    DISABLED = "disabled"


class HealthResponseStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FAIL = "fail"


class DependencyHealth(BaseModel):
    status: DependencyHealthStatus
    required: bool = False
    disabled: bool = False
    reason: str | None = None


class HealthChecks(BaseModel):
    database: DependencyHealth
    workspace: DependencyHealth
    ai: DependencyHealth
    vector_search: DependencyHealth
    jobs: DependencyHealth
    knowledge_assistant: DependencyHealth


class HealthResponse(BaseModel):
    ok: bool
    status: HealthResponseStatus
    checks: HealthChecks
