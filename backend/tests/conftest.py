from types import SimpleNamespace

import pytest

from jarvis import brain, config, llm


class FakeChat:
    """Stands in for a Gemini chat (domain agents): records messages and replies with a fixed text."""

    def __init__(self, system_prompt, tools, model, reply="ok"):
        self.system_prompt, self.tools, self.model, self.reply = system_prompt, tools, model, reply
        self.sent: list[str] = []

    def send_message(self, text):
        self.sent.append(text)
        return SimpleNamespace(text=self.reply)


class FakeBrainChat(FakeChat):
    """Stands in for JARVIS's Claude chat: same recording, but replies with plain text."""

    def send(self, text):
        self.sent.append(text)
        return self.reply


@pytest.fixture
def chats(monkeypatch):
    """Replace llm.make_chat (Gemini, used by domain agents) with FakeChat; returns the chats created."""
    made: list[FakeChat] = []

    def fake_make_chat(system_prompt, tools, model, temperature=0.4):
        chat = FakeChat(system_prompt, tools, model)
        made.append(chat)
        return chat

    monkeypatch.setattr(llm, "make_chat", fake_make_chat)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    return made


@pytest.fixture
def brain_chats(monkeypatch):
    """Replace the brain's ClaudeChat with FakeBrainChat; returns the list of brain chats created."""
    made: list[FakeBrainChat] = []

    def fake_chat(system_prompt, tools, model):
        chat = FakeBrainChat(system_prompt, tools, model)
        made.append(chat)
        return chat

    monkeypatch.setattr(brain, "ClaudeChat", fake_chat)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    return made
