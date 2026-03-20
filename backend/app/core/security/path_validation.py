"""Validation helpers for Unity Catalog volume paths."""

from pathlib import PurePosixPath

from app.core.errors import PathValidationError


def validate_volume_path(relative_path: str) -> str:
    """Validate and normalize a relative volume path.

    Returns the cleaned path string. Raises ``PathValidationError`` for
    empty, absolute, traversal, or otherwise malformed paths.
    """
    if not relative_path or not relative_path.strip():
        raise PathValidationError("Path must not be empty")

    if "\x00" in relative_path:
        raise PathValidationError("Null bytes in path are not allowed")

    path = PurePosixPath(relative_path)

    if path.is_absolute():
        raise PathValidationError("Absolute paths are not allowed")

    for part in path.parts:
        if part == "..":
            raise PathValidationError("Path traversal (..) is not allowed")

    normalized = str(path)
    if not normalized or normalized == ".":
        raise PathValidationError("Path must not be empty after normalization")

    return normalized
