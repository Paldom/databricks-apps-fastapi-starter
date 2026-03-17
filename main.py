"""Root shim – keeps ``main:app`` and ``main:create_app`` working for uvicorn / app.yaml."""
from app.main import app, create_app  # noqa: F401
