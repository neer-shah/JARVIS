import pytest

from jarvis.agents.base import AGENT_RULES, Agent

from .fakes import FakeAgent, FakeToolset


def test_as_tool_has_routable_name_and_docstring():
    tool = FakeAgent().as_tool()
    assert tool.__name__ == "music_agent"
    assert "Music agent for tests." in tool.__doc__
    assert "request:" in tool.__doc__


def test_agent_forwards_request_and_keeps_one_chat(chats):
    agent = FakeAgent()
    tool = agent.as_tool()
    assert tool("make a chill playlist") == "ok"
    assert tool("add five more") == "ok"
    assert len(chats) == 1  # follow-ups reuse the same history
    chat = chats[0]
    assert chat.sent == ["make a chill playlist", "add five more"]
    assert chat.model == "claude-haiku-5-5"
    assert chat.system_prompt.startswith("You play music.") and AGENT_RULES in chat.system_prompt
    assert [fn.__name__ for fn in chat.tools] == ["music_pause", "music_make_playlist", "music_broken"]


def test_tool_errors_become_friendly_text():
    broken = next(fn for fn in FakeAgent().tools() if fn.__name__ == "music_broken")
    assert broken() == "Error: boom"


def test_unknown_fast_tool_name_is_caught():
    class Typo(Agent):
        name = "typo"
        description = "x"
        system_prompt = "x"
        fast_tool_names = ("music_paws",)

    with pytest.raises(ValueError, match="unknown fast tools"):
        Typo(FakeToolset()).tools()
