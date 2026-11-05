import pytest

from jarvis.brain import Brain

from .fakes import FakeAgent, FakeEnv


def test_brain_sees_agent_tool_fast_tools_and_plain_tools_only(brain_chats):
    brain = Brain(agents=[FakeAgent()], environments=[FakeEnv()])
    assert sorted(brain.tool_names) == ["get_time", "music_agent", "music_pause"]
    assert [fn.__name__ for fn in brain_chats[0].tools] == brain.tool_names


def test_fast_tool_runs_without_a_sub_agent_chat(brain_chats, chats):
    agent = FakeAgent()
    brain = Brain(agents=[agent], environments=[])
    pause = next(fn for fn in brain_chats[0].tools if fn.__name__ == "music_pause")
    assert pause() == "Paused."
    assert agent.toolset.calls == ["pause"]
    assert chats == []  # the domain agent's Gemini chat was never created
    assert brain.modules() == {"music": ["music_pause", "music_make_playlist", "music_broken"]}


def test_duplicate_tool_names_are_rejected(brain_chats):
    with pytest.raises(ValueError, match="Duplicate"):
        Brain(agents=[FakeAgent(), FakeAgent()], environments=[])


def test_ask_returns_model_text(brain_chats):
    brain = Brain(agents=[], environments=[])
    assert brain.ask("hello") == "ok"
    assert brain_chats[0].sent[0] == "hello"


def test_brain_needs_an_anthropic_key(brain_chats, monkeypatch):
    from jarvis import config

    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", None)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Brain(agents=[], environments=[])
