from enum import Enum

from pydantic import BaseModel


class HealthCheckStatus(str, Enum):
    OK = "ok"
    FAIL = "fail"
    NOT_CONFIGURED = "not_configured"


class HealthReportStatus(str, Enum):
    ALIVE = "alive"
    READY = "ready"
    DEGRADED = "degraded"
    NOT_READY = "not_ready"


class HealthCheckResult(BaseModel):
    status: HealthCheckStatus
    required: bool
    message: str
    latency_ms: float | None = None


class HealthReport(BaseModel):
    ok: bool
    status: HealthReportStatus
    checks: dict[str, HealthCheckResult]
