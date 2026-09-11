"""Central MLflow runtime — single place for init, trace context, and trace ID extraction.

All MLflow bootstrapping and trace helpers live here.  The rest of the app
imports from this module instead of touching ``mlflow`` directly.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
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
    # MLflow 3 filters sessions/users on these metadata keys; the rest are tags.
    metadata: dict[str, str] = {}
    if session_id:
        metadata["mlflow.trace.session"] = session_id
    if user_id:
        metadata["mlflow.trace.user"] = user_id
    tags: dict[str, str] = {}
    if chat_id:
        tags["chat_id"] = chat_id
    if backend:
        tags["backend"] = backend
    if agent_kind:
        tags["agent.kind"] = agent_kind
    if agent_name:
        tags["agent.name"] = agent_name
    if not metadata and not tags:
        return
    try:
        import mlflow

        if mlflow.get_current_active_span() is None:  # e.g. background title generation
            return
        mlflow.update_current_trace(metadata=metadata or None, tags=tags or None)
    except Exception:
        logger.debug("update_current_trace failed", exc_info=True)


@contextmanager
def root_span(name: str) -> Iterator[Any]:
    """Open the agent root span so metadata and attributes have a trace to attach to.

    Autologged LangChain/OpenAI spans nest under it. Yields ``None`` when tracing is
    off; callers use :func:`stamp_span` which tolerates that.
    """
    if not _mlflow_enabled:
        yield None
        return
    import mlflow
    from mlflow.entities import SpanType

    with mlflow.start_span(name=name, span_type=SpanType.AGENT) as span:
        yield span


def stamp_span(
    span: Any,
    *,
    inputs: Any = None,
    outputs: Any = None,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Best-effort inputs/outputs/attributes on a span (None when tracing is off)."""
    if span is None:
        return
    try:
        if inputs is not None:
            span.set_inputs(inputs)
        if outputs is not None:
            span.set_outputs(outputs)
        if attributes:
            span.set_attributes({k: v for k, v in attributes.items() if v is not None})
    except Exception:
        logger.debug("stamping the root span failed", exc_info=True)


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
