from collections.abc import Callable

from . import config, llm
from .agents import Agent
from .agents import discover as discover_agents
from .environments import discover as discover_environments
from .environments.base import Environment


class Brain:
    """JARVIS's main model. It routes each request to a domain agent, a fast-path tool or a plain tool.

    Domain agents (Spotify, Calendar, ...) are exposed as one function each, `<name>_agent(request)`,
    so JARVIS never sees their internal tools. Simple commands (pause, skip, volume) are given to
    JARVIS directly via each agent's fast tools to skip the second model call.
    """

    def __init__(self, agents: list[Agent] | None = None, environments: list[Environment] | None = None):
        if not config.GEMINI_API_KEY:
            raise ValueError("GOOGLE_GENAI_API_KEY is not set (see .env).")
        self.agents = agents if agents is not None else discover_agents()
        self.environments = environments if environments is not None else discover_environments()

        tools: list[Callable[..., str]] = []
        for agent in self.agents:
            tools.append(llm.safe(agent.as_tool(), label="agent"))
            tools.extend(agent.fast_tools())  # already wrapped by the agent
        for env in self.environments:
            tools.extend(llm.safe(fn) for fn in env.tools())

        names = [fn.__name__ for fn in tools]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"Duplicate tool names: {duplicates}")
        self.tool_names = names
        print(f"[brain] agents: {[a.name for a in self.agents]}, tools: {sorted(names)}")

        self.chat = llm.make_chat(config.SYSTEM_PROMPT, tools, config.MODEL)

    def modules(self) -> dict[str, list[str]]:
        """Module name -> tool names, for display. Agents list their internal tools."""
        shown = {a.name: [fn.__name__ for fn in a.tools()] for a in self.agents}
        shown.update({e.name: [fn.__name__ for fn in e.tools()] for e in self.environments})
        return shown

    def ask(self, text: str) -> str:
        """Send one user utterance; returns the reply to speak. Conversation history is kept."""
        return llm.send(self.chat, text, who="brain")
