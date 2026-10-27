from types import SimpleNamespace

import pytest

from jarvis import config, llm


class FakeChat:
    """Stands in for a Gemini chat: records messages and replies with a fixed text."""

    def __init__(self, system_prompt, tools, model, reply="ok"):
        self.system_prompt, self.tools, self.model, self.reply = system_prompt, tools, model, reply
        self.sent: list[str] = []

    def send_message(self, text):
        self.sent.append(text)
        return SimpleNamespace(text=self.reply)


@pytest.fixture
def chats(monkeypatch):
    """Replace llm.make_chat with FakeChat; returns the list of chats created."""
    made: list[FakeChat] = []

    def fake_make_chat(system_prompt, tools, model, temperature=0.4):
        chat = FakeChat(system_prompt, tools, model)
        made.append(chat)
        return chat

    monkeypatch.setattr(llm, "make_chat", fake_make_chat)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    return made
