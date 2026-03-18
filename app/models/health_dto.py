from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class DependencyHealthStatus(str, Enum):
    OK = "ok"
    FAIL = "fail"
    NOT_CONFIGURED = "not_configured"
    DISABLED = "disabled"


class HealthResponseStatus(str, Enum):
    ALIVE = "alive"
    READY = "ready"
    DEGRADED = "degraded"
    NOT_READY = "not_ready"


class DependencyHealth(BaseModel):
    status: DependencyHealthStatus
    required: bool = False
    disabled: bool = False
    reason: str | None = None


class LiveHealthResponse(BaseModel):
    status: HealthResponseStatus


class ReadyHealthResponse(BaseModel):
    ok: bool
    status: HealthResponseStatus
    db: DependencyHealth


class IntegrationsHealthResponse(BaseModel):
    ok: bool
    status: HealthResponseStatus
    workspace: DependencyHealth
    ai: DependencyHealth
    vector_search: DependencyHealth
