"""Root shim – keeps ``api_router`` importable from the project root."""
from app.api.api import api_router  # noqa: F401
