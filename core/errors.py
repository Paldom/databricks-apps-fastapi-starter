from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException

DEFAULT_ERROR_MESSAGES = {status.value: status.phrase for status in HTTPStatus}


def http_error(status_code: int, detail: Optional[str] = None) -> HTTPException:
    """Return an :class:`HTTPException` with a standardized message."""
    message = detail or DEFAULT_ERROR_MESSAGES.get(status_code, "Unknown Error")
    return HTTPException(status_code=status_code, detail=message)
