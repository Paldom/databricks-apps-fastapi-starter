"""Module spec: hosted multi-agent supervisor as a chat specialist.

Activates when ``MAS_ENDPOINT`` (Settings ``mas_endpoint``) names a serving
endpoint hosting an Agent Bricks Multi-Agent Supervisor or any
``langgraph_supervisor``-style agent. The app's own LangGraph supervisor then
gains one extra tool that hands whole questions to that remote supervisor —
agents supervising agents, still on the one Responses contract (DESIGN.md).
"""

from app.chat.registry import SpecialistSpec
from app.modules.registry import ModuleSpec
from app.modules.supervisor_agent.tool import build_mas_tool

spec = ModuleSpec(
    name="supervisor-agent",
    title="Multi-agent supervisor (Agent Bricks / langgraph_supervisor)",
    description=(
        "Forwards complex questions to a Databricks-hosted multi-agent "
        "supervisor endpoint over the Responses API — the managed "
        "counterpart of this app's in-process LangGraph supervisor."
    ),
    config_keys=("mas_endpoint",),
    specialist=SpecialistSpec(
        key="multi_agent_supervisor",
        description=(
            "Delegate complex, multi-domain, or cross-team questions to a "
            "hosted multi-agent supervisor that coordinates its own team "
            "of specialist agents."
        ),
        kind="multi_agent_supervisor",
    ),
    tool_builder=build_mas_tool,
)
