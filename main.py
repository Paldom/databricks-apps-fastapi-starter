"""Root shim – keeps ``main:app`` working for uvicorn / app.yaml."""
from app.main import app  # noqa: F401
