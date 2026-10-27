from jarvis.agents.base import Agent
from jarvis.environments.base import Environment


class FakeToolset(Environment):
    name = "music"

    def __init__(self):
        self.calls: list[str] = []

    def tools(self):
        def music_pause() -> str:
            """Pause."""
            self.calls.append("pause")
            return "Paused."

        def music_make_playlist(name: str) -> str:
            """Make a playlist."""
            self.calls.append(f"make {name}")
            return f"Created {name}."

        def music_broken() -> str:
            """Always fails."""
            raise RuntimeError("boom")

        return [music_pause, music_make_playlist, music_broken]


class FakeAgent(Agent):
    name = "music"
    description = "Music agent for tests."
    system_prompt = "You play music."
    fast_tool_names = ("music_pause",)

    def __init__(self):
        super().__init__(FakeToolset())


class FakeEnv(Environment):
    name = "clock"

    def tools(self):
        def get_time() -> str:
            """Time."""
            return "noon"

        return [get_time]
