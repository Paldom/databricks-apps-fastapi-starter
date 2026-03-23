"""Tests for the specialist registry."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.chat.registry import (
    SPECIALISTS,
    build_routing_instructions,
    build_supervisor_prompt,
    get_enabled_specs,
)


def _settings(**overrides):
    s = MagicMock()
    s.app_agent_name = overrides.get("app_agent_name", None)
    s.genie_space_id = overrides.get("genie_space_id", None)
    s.ai_gateway_embedding_model = overrides.get("ai_gateway_embedding_model", None)
    s.knowledge_assistant_endpoint = overrides.get("knowledge_assistant_endpoint", None)
    s.serving_agent_endpoint = overrides.get("serving_agent_endpoint", None)
    return s


class TestGetEnabledSpecs:
    def test_nothing_enabled(self):
        specs = get_enabled_specs(_settings())
        assert len(specs) == 0

    def test_all_enabled(self):
        specs = get_enabled_specs(
            _settings(
                app_agent_name="my-app",
                genie_space_id="genie-123",
                ai_gateway_embedding_model="bge-large",
                serving_agent_endpoint="my-endpoint",
            )
        )
        assert len(specs) == 4
        keys = {s.key for s in specs}
        assert keys == {"app_agent", "genie", "knowledge_assistant", "serving_endpoint"}

    def test_partial_enabled(self):
        specs = get_enabled_specs(_settings(genie_space_id="genie-123"))
        assert len(specs) == 1
        assert specs[0].key == "genie"


class TestBuildRoutingInstructions:
    def test_empty_specs(self):
        result = build_routing_instructions([])
        assert "No specialist tools" in result

    def test_includes_all_spec_keys(self):
        result = build_routing_instructions(SPECIALISTS)
        for spec in SPECIALISTS:
            assert spec.key in result


class TestBuildSupervisorPrompt:
    def test_includes_preamble(self):
        prompt = build_supervisor_prompt([])
        assert "chat supervisor" in prompt

    def test_includes_routing_for_enabled_specs(self):
        specs = [SPECIALISTS[1]]  # genie
        prompt = build_supervisor_prompt(specs)
        assert "genie" in prompt
