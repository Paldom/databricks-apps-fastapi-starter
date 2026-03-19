from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Application-level exception hierarchy
# ---------------------------------------------------------------------------

class AppError(Exception):
    """Base application exception carrying an HTTP-mappable status code."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        cause: Exception | None = None,
    ):
        self.status_code = status_code
        self.detail = detail
        self.cause = cause
        super().__init__(detail)


class NotFoundError(AppError):
    def __init__(self, detail: str = "Not found", **kw):
        super().__init__(404, detail, **kw)


class AuthenticationError(AppError):
    def __init__(self, detail: str = "Authentication required", **kw):
        super().__init__(401, detail, **kw)


class ConfigurationError(AppError):
    def __init__(self, detail: str = "Service not configured", **kw):
        super().__init__(503, detail, **kw)


class ServiceUnavailableError(AppError):
    def __init__(self, detail: str = "Service unavailable", **kw):
        super().__init__(503, detail, **kw)


class ExternalServiceError(AppError):
    def __init__(self, detail: str = "External service error", **kw):
        super().__init__(502, detail, **kw)


# Adapter-specific errors
class DatabricksAPIError(ExternalServiceError):
    pass


class ServingEndpointError(ExternalServiceError):
    pass


class JobExecutionError(ExternalServiceError):
    pass


class AiGatewayError(ExternalServiceError):
    pass


class VectorSearchError(ExternalServiceError):
    pass


class SqlDeltaError(ExternalServiceError):
    def __init__(self, detail: str = "SQL execution error", **kw):
        super().__init__(detail, **kw)
        self.status_code = 500


class GenieError(ExternalServiceError):
    pass


class KnowledgeAssistantError(ExternalServiceError):
    pass


class UcFilesError(ExternalServiceError):
    pass


class RequestTooLargeError(AppError):
    def __init__(self, detail: str = "Request body too large", **kw):
        super().__init__(413, detail, **kw)


class RequestTimeoutError(AppError):
    def __init__(self, detail: str = "Request timed out", **kw):
        super().__init__(504, detail, **kw)


class PathValidationError(AppError):
    def __init__(self, detail: str = "Invalid path", **kw):
        super().__init__(400, detail, **kw)


class ResourceNotFoundError(AppError):
    def __init__(self, detail: str = "Resource not found", **kw):
        super().__init__(404, detail, **kw)


# ---------------------------------------------------------------------------
# Backward-compatible HTTP error helper
# ---------------------------------------------------------------------------

DEFAULT_ERROR_MESSAGES = {status.value: status.phrase for status in HTTPStatus}


def http_error(status_code: int, detail: Optional[str] = None) -> HTTPException:
    """Return an :class:`HTTPException` with a standardized message."""
    message = detail or DEFAULT_ERROR_MESSAGES.get(status_code, "Unknown Error")
    return HTTPException(status_code=status_code, detail=message)
