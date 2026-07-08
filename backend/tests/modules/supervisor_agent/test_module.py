"""Activation tests for the supervisor-agent module spec."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.core.config import Settings
from app.modules.supervisor_agent.module import spec
from app.modules.supervisor_agent.tool import build_mas_tool


class TestModuleSpec:
    def test_name_matches_folder_and_resource_file(self):
        assert spec.name == "supervisor-agent"

    def test_gates_on_mas_endpoint(self):
        assert spec.config_keys == ("mas_endpoint",)

    def test_specialist_contribution_is_wired(self):
        assert spec.specialist is not None
        assert spec.specialist.key == "multi_agent_supervisor"
        assert spec.specialist.kind == "multi_agent_supervisor"
        assert spec.tool_builder is build_mas_tool


class TestActivation:
    def test_inactive_without_mas_endpoint(self, monkeypatch):
        monkeypatch.delenv("MAS_ENDPOINT", raising=False)
        settings = Settings(_env_file=None)
        assert spec.is_active(settings) is False

    def test_inactive_when_endpoint_empty(self):
        settings = MagicMock()
        settings.mas_endpoint = ""
        assert spec.is_active(settings) is False

    def test_active_when_endpoint_configured(self):
        settings = MagicMock()
        settings.mas_endpoint = "mas-supervisor"
        assert spec.is_active(settings) is True
