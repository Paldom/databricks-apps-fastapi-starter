"""Tests for the central MLflow runtime module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestConfigureMlflow:
    """configure_mlflow() init tests."""

    def test_disabled_when_no_experiment(self):
        from app.core.mlflow_runtime import configure_mlflow, is_mlflow_enabled

        result = configure_mlflow(None)
        assert result is False
        assert is_mlflow_enabled() is False

    def test_disabled_with_empty_string(self):
        from app.core.mlflow_runtime import configure_mlflow

        result = configure_mlflow("")
        assert result is False

    def test_enabled_with_experiment_id(self):
        """When experiment ID is provided, MLflow is initialized."""
        from app.core.mlflow_runtime import configure_mlflow, is_mlflow_enabled

        # MLflow is installed in this env; configure_mlflow should succeed
        # (may warn about tracking URI, but should not raise)
        with patch("mlflow.set_experiment"), \
             patch("mlflow.langchain.autolog"), \
             patch("mlflow.openai.autolog"):
            result = configure_mlflow("12345")
            assert result is True
            assert is_mlflow_enabled() is True


class TestExtractTraceId:
    """extract_trace_id() handles various payload shapes."""

    def setup_method(self):
        from app.core.mlflow_runtime import extract_trace_id

        self.extract = extract_trace_id

    def test_none_payload(self):
        assert self.extract(None) is None

    def test_empty_dict(self):
        assert self.extract({}) is None

    def test_direct_trace_id_in_dict(self):
        assert self.extract({"trace_id": "tr-abc123"}) == "tr-abc123"

    def test_metadata_trace_id(self):
        payload = {"metadata": {"trace_id": "tr-meta-1"}}
        assert self.extract(payload) == "tr-meta-1"

    def test_databricks_output_trace_id(self):
        payload = {
            "databricks_output": {
                "trace": {"trace_id": "tr-db-1"}
            }
        }
        assert self.extract(payload) == "tr-db-1"

    def test_sdk_object_with_metadata(self):
        obj = MagicMock()
        obj.metadata = {"trace_id": "tr-sdk-1"}
        obj.databricks_output = None
        assert self.extract(obj) == "tr-sdk-1"

    def test_sdk_object_with_databricks_output(self):
        obj = MagicMock(spec=[])
        obj.metadata = None
        obj.databricks_output = {"trace": {"trace_id": "tr-sdk-db-1"}}
        assert self.extract(obj) == "tr-sdk-db-1"

    def test_missing_trace_id_returns_none(self):
        payload = {"metadata": {"other": "stuff"}}
        assert self.extract(payload) is None

    def test_nested_empty_returns_none(self):
        payload = {"databricks_output": {"trace": {}}}
        assert self.extract(payload) is None


class TestGetActiveTraceId:
    """get_active_trace_id() is best-effort."""

    def test_returns_none_when_mlflow_unavailable(self):
        from app.core.mlflow_runtime import get_active_trace_id

        # MLflow may be stubbed in test env, should not raise
        result = get_active_trace_id()
        assert result is None or isinstance(result, str)


class TestUpdateTraceContext:
    """update_trace_context() is best-effort."""

    def test_no_op_with_no_metadata(self):
        from app.core.mlflow_runtime import update_trace_context

        # Should not raise
        update_trace_context()

    def test_handles_mlflow_unavailable(self):
        from app.core.mlflow_runtime import update_trace_context

        # Should not raise even if mlflow is stubbed
        update_trace_context(session_id="test", user_id="u1")
