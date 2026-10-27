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
    assert chat.sent[0].endswith("make a chill playlist") and chat.sent[0].startswith("[Current local time:")
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


def test_agent_retries_less_than_brain(chats, monkeypatch):
    from google.genai import errors

    from jarvis import llm

    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    agent = FakeAgent()
    agent.run("warm up")
    attempts = []

    def overloaded(text):
        attempts.append(text)
        raise errors.APIError(503, {"error": {"message": "overloaded"}})

    chats[0].send_message = overloaded
    assert "overloaded" in agent.run("play something")
    assert len(attempts) == 2  # one try plus one retry
