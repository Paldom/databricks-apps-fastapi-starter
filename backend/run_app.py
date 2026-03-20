"""Databricks Apps entrypoint.

When deployed via ``databricks bundle``, the working directory is the
bundle root (repo root).  This script adds ``backend/`` to sys.path so
that ``app.*`` imports resolve correctly, then starts uvicorn.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("DATABRICKS_APP_PORT", "8000")),
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info"),
    )
