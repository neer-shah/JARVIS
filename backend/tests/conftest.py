import pytest

from jarvis import brain, config
from jarvis.agents import base as agent_base


class FakeChat:
    """Stands in for a ClaudeChat: records what it was sent and replies with a fixed text."""

    def __init__(self, system_prompt, tools, model, reply="ok"):
        self.system_prompt, self.tools, self.model, self.reply = system_prompt, tools, model, reply
        self.sent: list[str] = []

    def send(self, text):
        self.sent.append(text)
        return self.reply


@pytest.fixture
def chats(monkeypatch):
    """Replace ClaudeChat in the brain and in domain agents with FakeChat; returns every chat created."""
    made: list[FakeChat] = []

    def fake_chat(system_prompt, tools, model):
        chat = FakeChat(system_prompt, tools, model)
        made.append(chat)
        return chat

    monkeypatch.setattr(brain, "ClaudeChat", fake_chat)
    monkeypatch.setattr(agent_base, "ClaudeChat", fake_chat)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    return made
