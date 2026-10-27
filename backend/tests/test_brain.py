import pytest

from jarvis.brain import Brain

from .fakes import FakeAgent, FakeEnv


def test_brain_sees_agent_tool_fast_tools_and_plain_tools_only(chats):
    brain = Brain(agents=[FakeAgent()], environments=[FakeEnv()])
    assert sorted(brain.tool_names) == ["get_time", "music_agent", "music_pause"]
    assert [fn.__name__ for fn in chats[0].tools] == brain.tool_names


def test_fast_tool_runs_without_a_sub_agent_chat(chats):
    agent = FakeAgent()
    brain = Brain(agents=[agent], environments=[])
    pause = next(fn for fn in chats[0].tools if fn.__name__ == "music_pause")
    assert pause() == "Paused."
    assert agent.toolset.calls == ["pause"]
    assert len(chats) == 1  # only JARVIS's own chat, no agent chat was created
    assert brain.modules() == {"music": ["music_pause", "music_make_playlist", "music_broken"]}


def test_duplicate_tool_names_are_rejected(chats):
    with pytest.raises(ValueError, match="Duplicate"):
        Brain(agents=[FakeAgent(), FakeAgent()], environments=[])


def test_ask_returns_model_text(chats):
    brain = Brain(agents=[], environments=[])
    assert brain.ask("hello") == "ok"
    assert chats[0].sent[0].endswith("hello")


def test_echoed_time_stamp_is_not_spoken(chats):
    brain = Brain(agents=[], environments=[])
    chats[0].reply = "[20:27] You have nothing on tomorrow."
    assert brain.ask("what's on?") == "You have nothing on tomorrow."
