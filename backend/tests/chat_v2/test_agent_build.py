"""build_agent must compile against the installed langgraph.

Guards against prebuilt-API drift (e.g. langgraph requiring
``remaining_steps`` in custom state schemas), which only surfaces when the
real ``create_react_agent`` runs — mocks don't catch it.
"""

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import MemorySaver

from app.chat.agent import build_agent


def test_build_agent_compiles_with_real_langgraph():
    agent = build_agent(
        model=FakeListChatModel(responses=["ok"]),
        tools=[],
        prompt="You are a test.",
        checkpointer=MemorySaver(),
    )
    assert agent is not None
    assert hasattr(agent, "astream")
