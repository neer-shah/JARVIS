import pytest

from jarvis.agents.calendar.agent import CalendarAgent as AgentCls
from jarvis.agents.calendar.tools import Calendar


@pytest.fixture(autouse=True)
def no_icloud_login(monkeypatch):
    monkeypatch.setattr(Calendar, "_warm", lambda self: None)


def test_fast_tools_exist_and_tools_are_prefixed():
    agent = AgentCls()
    names = [fn.__name__ for fn in agent.toolset.tools()]
    assert all(n.startswith("calendar_") for n in names)
    assert set(agent.fast_tool_names) <= set(names)


def test_agent_tool_is_named_for_routing():
    assert AgentCls().as_tool().__name__ == "calendar_agent"
