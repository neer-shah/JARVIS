from jarvis.agents.spotify.agent import SpotifyAgent as AgentCls


def test_fast_tools_exist_and_tools_are_prefixed():
    agent = AgentCls()
    names = [fn.__name__ for fn in agent.toolset.tools()]
    assert all(n.startswith("spotify_") for n in names)
    assert set(agent.fast_tool_names) <= set(names)


def test_agent_tool_is_named_for_routing():
    assert AgentCls().as_tool().__name__ == "spotify_agent"
