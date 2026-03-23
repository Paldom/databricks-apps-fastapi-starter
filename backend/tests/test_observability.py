"""Tests for observability helpers and OTel configuration."""

from __future__ import annotations

import yaml

from app.core.observability import safe_attr, tag_exception


class TestSafeAttr:
    def test_none_returns_empty_string(self):
        assert safe_attr(None) == ""

    def test_bool_passes_through(self):
        assert safe_attr(True) is True
        assert safe_attr(False) is False

    def test_int_passes_through(self):
        assert safe_attr(42) == 42

    def test_float_passes_through(self):
        assert safe_attr(3.14) == 3.14

    def test_string_passes_through(self):
        assert safe_attr("hello") == "hello"

    def test_long_string_truncated(self):
        long = "x" * 300
        result = safe_attr(long)
        assert len(result) == 256

    def test_non_string_converted(self):
        result = safe_attr(["a", "b"])
        assert isinstance(result, str)


class TestTagException:
    def test_sets_error_status_and_records(self):
        from unittest.mock import MagicMock

        span = MagicMock()
        exc = ValueError("test error")
        tag_exception(span, exc)
        span.set_status.assert_called_once()
        span.record_exception.assert_called_once_with(exc)


class TestLoggingFieldNames:
    def test_uses_correct_otel_field_names(self):
        from app.core.logging import _LOCAL_FORMAT, _FORMAT_DEFAULTS

        # OpenTelemetry Python uses otelTraceID (capital ID), not otelTraceId
        assert "otelTraceID" in _LOCAL_FORMAT
        assert "otelSpanID" in _LOCAL_FORMAT
        assert "otelTraceID" in _FORMAT_DEFAULTS
        assert "otelSpanID" in _FORMAT_DEFAULTS


class TestDatabricksAppCommand:
    def test_command_uses_opentelemetry_instrument(self):
        with open("../databricks.yml") as f:
            bundle = yaml.safe_load(f)

        # Default app_config command must include opentelemetry-instrument
        default_cmd = bundle["variables"]["app_config"]["default"]["command"]
        assert default_cmd[0] == "opentelemetry-instrument", (
            f"Default app command should start with opentelemetry-instrument, got: {default_cmd}"
        )

        # Every target override must also include opentelemetry-instrument
        for name, target in bundle.get("targets", {}).items():
            override = target.get("variables", {}).get("app_config")
            if override is None:
                continue
            cmd = override.get("command", [])
            assert cmd and cmd[0] == "opentelemetry-instrument", (
                f"Target '{name}' app_config command must start with "
                f"opentelemetry-instrument, got: {cmd}"
            )
