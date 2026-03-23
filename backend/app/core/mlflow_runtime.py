"""Central MLflow runtime — single place for init, trace context, and trace ID extraction.

All MLflow bootstrapping and trace helpers live here.  The rest of the app
imports from this module instead of touching ``mlflow`` directly.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_mlflow_enabled: bool = False


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def configure_mlflow(experiment_id: str | None) -> bool:
    """Initialize MLflow once.  Returns *True* if tracing is active."""
    global _mlflow_enabled

    if not experiment_id:
        logger.info("MLflow tracing disabled: no experiment configured")
        _mlflow_enabled = False
        return False

    import mlflow

    os.environ.setdefault("MLFLOW_TRACKING_URI", "databricks")
    os.environ.setdefault("MLFLOW_REGISTRY_URI", "databricks-uc")

    mlflow.set_experiment(experiment_id=experiment_id)

    mlflow.langchain.autolog(
        disable_for_unsupported_versions=True,
        silent=True,
        log_traces=True,
    )
    logger.info("MLflow LangChain autolog enabled (experiment=%s)", experiment_id)

    try:
        mlflow.openai.autolog(
            disable_for_unsupported_versions=True,
            silent=True,
            log_traces=True,
        )
    except Exception:
        logger.debug("MLflow OpenAI autolog unavailable", exc_info=True)

    _mlflow_enabled = True
    return True


def is_mlflow_enabled() -> bool:
    return _mlflow_enabled


# ---------------------------------------------------------------------------
# Trace context
# ---------------------------------------------------------------------------


def update_trace_context(
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    chat_id: str | None = None,
    backend: str | None = None,
    agent_kind: str | None = None,
    agent_name: str | None = None,
) -> None:
    """Attach metadata to the current MLflow trace (best-effort)."""
    metadata: dict[str, str] = {}
    if session_id:
        metadata["mlflow.trace.session"] = session_id
    if user_id:
        metadata["user_id"] = user_id
    if chat_id:
        metadata["chat_id"] = chat_id
    if backend:
        metadata["backend"] = backend
    if agent_kind:
        metadata["agent.kind"] = agent_kind
    if agent_name:
        metadata["agent.name"] = agent_name

    if not metadata:
        return

    try:
        import mlflow

        mlflow.update_current_trace(tags=metadata)
    except Exception:
        logger.debug("update_current_trace failed", exc_info=True)


# ---------------------------------------------------------------------------
# Active / root trace ID
# ---------------------------------------------------------------------------


def get_active_trace_id() -> str | None:
    """Return the active MLflow trace ID, or *None* if unavailable."""
    try:
        import mlflow

        return mlflow.get_active_trace_id()  # type: ignore[return-value]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Downstream trace-ID extraction
# ---------------------------------------------------------------------------


def extract_trace_id(payload: Any) -> str | None:
    """Extract a downstream MLflow trace ID from a response payload.

    Supports:
    - ``metadata.trace_id`` (Responses API)
    - ``databricks_output.trace.trace_id`` (chat completions)
    - raw dict equivalents
    """
    if payload is None:
        return None

    # ── Raw dict ──────────────────────────────────────────────────
    if isinstance(payload, dict):
        direct = payload.get("trace_id")
        if direct:
            return str(direct)

        md = payload.get("metadata")
        if isinstance(md, dict) and md.get("trace_id"):
            return str(md["trace_id"])

        db_out = payload.get("databricks_output")
        if isinstance(db_out, dict):
            trace = db_out.get("trace") or {}
            if isinstance(trace, dict) and trace.get("trace_id"):
                return str(trace["trace_id"])

        return None

    # ── SDK object with metadata ──────────────────────────────────
    md = getattr(payload, "metadata", None)
    if isinstance(md, dict) and md.get("trace_id"):
        return str(md["trace_id"])

    # ── SDK object with databricks_output ─────────────────────────
    db_out = getattr(payload, "databricks_output", None)
    if isinstance(db_out, dict):
        trace = db_out.get("trace") or {}
        if isinstance(trace, dict) and trace.get("trace_id"):
            return str(trace["trace_id"])

    return None
